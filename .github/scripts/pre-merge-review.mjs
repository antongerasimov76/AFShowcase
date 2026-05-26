import { readFile } from 'node:fs/promises';

const token = requiredEnv('GITHUB_TOKEN');
const repository = requiredEnv('GITHUB_REPOSITORY');
const prNumber = Number(requiredEnv('PR_NUMBER'));
const model = process.env.PRE_MERGE_REVIEW_MODEL || 'openai/gpt-4.1';
const waitForStage1 = process.env.WAIT_FOR_STAGE1 === 'true';

const [owner, repo] = repository.split('/');
const apiBase = 'https://api.github.com';
const markerPrefix = `<!-- pre-merge-review-action pr:${prNumber}`;

if (!owner || !repo || Number.isNaN(prNumber)) {
  throw new Error(`Invalid repository or PR number: repository=${repository}, prNumber=${process.env.PR_NUMBER}`);
}

const pr = await github(`/repos/${owner}/${repo}/pulls/${prNumber}`);

if (waitForStage1) {
  await waitForCopilotStage1();
}

const [files, issueComments, reviews, checkRuns, copilotInstructions, reviewTemplate] = await Promise.all([
  paginate(`/repos/${owner}/${repo}/pulls/${prNumber}/files`),
  paginate(`/repos/${owner}/${repo}/issues/${prNumber}/comments`),
  paginate(`/repos/${owner}/${repo}/pulls/${prNumber}/reviews`),
  getCheckRuns(pr.head.sha),
  readOptional('.github/copilot-instructions.md'),
  readOptional('.github/instructions/code-review.instructions.md')
]);

const review = await buildReview({
  pr,
  files,
  issueComments,
  reviews,
  checkRuns,
  copilotInstructions,
  reviewTemplate
});

await upsertReviewComment(pr, review, issueComments);

function requiredEnv(name) {
  const value = process.env[name];
  if (!value) {
    throw new Error(`Missing required environment variable: ${name}`);
  }
  return value;
}

async function github(path, options = {}) {
  const response = await fetch(`${apiBase}${path}`, {
    ...options,
    headers: {
      Accept: 'application/vnd.github+json',
      Authorization: `Bearer ${token}`,
      'X-GitHub-Api-Version': '2022-11-28',
      ...(options.headers || {})
    }
  });

  const text = await response.text();
  const data = text ? JSON.parse(text) : null;

  if (!response.ok) {
    const message = data?.message || response.statusText;
    throw new Error(`GitHub API ${response.status} for ${path}: ${message}`);
  }

  return data;
}

async function paginate(path) {
  const results = [];
  let page = 1;

  for (;;) {
    const separator = path.includes('?') ? '&' : '?';
    const pageData = await github(`${path}${separator}per_page=100&page=${page}`);
    results.push(...pageData);

    if (pageData.length < 100) {
      return results;
    }

    page += 1;
  }
}

async function getCheckRuns(sha) {
  try {
    const data = await github(`/repos/${owner}/${repo}/commits/${sha}/check-runs?per_page=100`, {
      headers: { Accept: 'application/vnd.github+json' }
    });
    return data.check_runs || [];
  } catch (error) {
    console.warn(`Could not read check runs: ${error.message}`);
    return [];
  }
}

async function readOptional(path) {
  try {
    return await readFile(path, 'utf8');
  } catch {
    return '';
  }
}

async function waitForCopilotStage1() {
  const maxAttempts = 20;
  const delayMs = 30000;

  for (let attempt = 1; attempt <= maxAttempts; attempt += 1) {
    const reviews = await paginate(`/repos/${owner}/${repo}/pulls/${prNumber}/reviews`);
    const found = reviews.some(review => review.user?.login === 'copilot-pull-request-reviewer[bot]');

    if (found) {
      console.log(`Stage 1 review found on attempt ${attempt}.`);
      return;
    }

    if (attempt < maxAttempts) {
      console.log(`Stage 1 review not found (${attempt}/${maxAttempts}); waiting ${delayMs / 1000}s.`);
      await new Promise(resolve => setTimeout(resolve, delayMs));
    }
  }

  console.warn('Stage 1 review not found before timeout. Continuing with deep review.');
}

async function buildReview(context) {
  const prompt = createPrompt(context);

  try {
    const aiReview = await callGitHubModels(prompt);
    return normalizeReview(aiReview, context);
  } catch (error) {
    console.warn(`GitHub Models review failed; using fallback review. ${error.message}`);
    return fallbackReview(context, error);
  }
}

function createPrompt({ pr, files, issueComments, reviews, checkRuns, copilotInstructions, reviewTemplate }) {
  const latestStage1 = latestByUser(reviews, 'copilot-pull-request-reviewer[bot]')?.body || '';
  const latestActionComments = issueComments
    .filter(comment => comment.user?.login === 'github-actions[bot]' || comment.user?.login === 'Copilot')
    .slice(-5)
    .map(comment => `Author: ${comment.user.login}\n${truncate(comment.body || '', 3000)}`)
    .join('\n\n---\n\n');

  const fileContext = diffContext(files);
  const checks = checkRuns.map(check => ({
    name: check.name,
    status: check.status,
    conclusion: check.conclusion,
    url: check.html_url
  }));

  return [
    {
      role: 'system',
      content: [
        'You are a read-only pre-merge code reviewer running inside GitHub Actions.',
        'You cannot edit files, cannot commit, and cannot push. Never claim that you fixed or changed code.',
        'Your only deliverable is a markdown PR comment.',
        'Return only the review comment body. Do not include preambles or meta commentary.',
        'Use concrete file paths and line references where possible.',
        'If something cannot be verified, write MISSING - <action>.',
        'Do not expose secrets. If a secret-like value appears in the diff, redact it and describe the risk.'
      ].join('\n')
    },
    {
      role: 'user',
      content: [
        'Produce a pre-merge review for this pull request.',
        '',
        'Required output format:',
        '## Pre-Merge Review - Risk: <1-10>/10',
        '> Execution Context: GITHUB ACTIONS | Review Mode: CODE',
        '',
        '## Summary',
        '## Diff Coverage',
        '## CI Status Analysis',
        '## Changes Made',
        '### Per-file Review',
        '### Type of Change',
        '## Risks & Security',
        '### Testing',
        '## Code Quality',
        '## Documentation',
        '## Checklist',
        '## Merge Risk Score',
        '## Merge Readiness',
        '',
        'Rules:',
        '- Findings must be observations, not claims that you implemented fixes.',
        '- Do not say "completed", "fixed", "now fixed", or mention a commit you made.',
        '- Merge Readiness must be one of: Block, Needs follow-up items, LGTM.',
        '- Include the repository, PR branch, base branch, and head SHA near the top.',
        '',
        `Repository: ${repository}`,
        `PR: #${pr.number} ${pr.title}`,
        `Base: ${pr.base.ref}`,
        `Head: ${pr.head.ref}`,
        `Head SHA: ${pr.head.sha}`,
        `Author: ${pr.user?.login || 'unknown'}`,
        '',
        'PR body:',
        truncate(pr.body || 'No PR body.', 6000),
        '',
        'Check runs:',
        JSON.stringify(checks, null, 2),
        '',
        'Stage 1 review:',
        truncate(latestStage1 || 'No Stage 1 review found.', 12000),
        '',
        'Recent bot comments:',
        latestActionComments || 'None.',
        '',
        'Repository review instructions:',
        truncate(copilotInstructions || 'None.', 12000),
        '',
        'Strict template / format guidance:',
        truncate(reviewTemplate || 'None.', 12000),
        '',
        'Changed files and patches:',
        fileContext
      ].join('\n')
    }
  ];
}

async function callGitHubModels(messages) {
  const response = await fetch('https://models.github.ai/inference/chat/completions', {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      model,
      messages,
      temperature: 0.1,
      max_tokens: 6000
    })
  });

  const text = await response.text();
  const data = text ? JSON.parse(text) : null;

  if (!response.ok) {
    const message = data?.error?.message || data?.message || response.statusText;
    throw new Error(`GitHub Models ${response.status}: ${message}`);
  }

  const content = data?.choices?.[0]?.message?.content;
  if (!content) {
    throw new Error('GitHub Models returned no message content.');
  }

  return content;
}

function normalizeReview(review, context) {
  let output = review.trim();

  output = output.replace(/\b(now fixed|fixed|completed \(commit [`a-f0-9]+`\)|commit [`a-f0-9]+`)\b/gi, 'identified');

  if (!output.startsWith('## Pre-Merge Review')) {
    output = `${header(context, 5)}\n\n${output}`;
  }

  return output;
}

function fallbackReview({ pr, files, reviews, checkRuns }, error) {
  const selectedFiles = selectFiles(files);
  const secretFindings = scanSecrets(files);
  const failedChecks = checkRuns.filter(check => check.conclusion && check.conclusion !== 'success' && check.conclusion !== 'skipped');
  const hasTests = files.some(file => /(^|\/)(tests?|__tests__|specs?)(\/|$)|(_test|\.test|\.spec)\./i.test(file.filename));
  const stage1 = latestByUser(reviews, 'copilot-pull-request-reviewer[bot]');
  const risk = calculateFallbackRisk(secretFindings, failedChecks, hasTests);

  return [
    header({ pr }, risk),
    '',
    '## Summary',
    `This PR changes ${files.length} file(s) on ${pr.head.ref} targeting ${pr.base.ref}. GitHub Models review was unavailable, so this comment was generated by the deterministic fallback reviewer.`,
    '',
    '## Diff Coverage',
    `- Files changed: ${files.length}. Reviewed ${selectedFiles.length}${files.length > selectedFiles.length ? ` top files by change size; ${files.length - selectedFiles.length} file(s) require manual review due to size limits.` : ' file(s).'}`,
    '',
    '## CI Status Analysis',
    checkSummary(checkRuns),
    '',
    '## Changes Made',
    ...selectedFiles.map(file => `- ${file.filename}: ${file.status}, +${file.additions}/-${file.deletions}`),
    '',
    '### Per-file Review',
    ...selectedFiles.flatMap(file => [
      `- **path:** \`${file.filename}\``,
      `  - Change summary: ${file.status}, +${file.additions}/-${file.deletions}.`,
      `  - Potential issues or nitpicks: ${file.patch ? summarizePatchRisk(file.patch) : 'MISSING - patch not available from GitHub API.'}`,
      '  - Concrete suggestions: MISSING - AI review unavailable; manually inspect the patch for project-specific behavior.'
    ]),
    '',
    '### Type of Change',
    '- [ ] Bug fix',
    '- [ ] New feature',
    '- [ ] Breaking change',
    '- [ ] Documentation update',
    '- [ ] Infrastructure change',
    '- [ ] Refactor',
    '- [ ] Security fix',
    'MISSING - classify the change type from PR intent.',
    '',
    '## Risks & Security',
    `- Secrets or tokens added? ${secretFindings.length ? 'Yes - BLOCKS MERGE until verified and removed/rotated.' : 'No obvious secret-like additions detected by fallback scan.'}`,
    '- Hardcoded connection strings? MISSING - manually verify.',
    '- Hardcoded API keys or endpoints? MISSING - manually verify.',
    '- Input validation present for all user inputs? MISSING - manually verify.',
    '- `.gitignore` properly configured for `local.settings.json`? MISSING - manually verify.',
    ...secretFindings.map(finding => `- Secret-like addition: ${finding.file} (${finding.reason})`),
    '',
    '### Testing',
    hasTests ? '- Tests appear to be added or updated.' : '- MISSING - add/point to tests or document why tests are not applicable.',
    '',
    '## Code Quality',
    '- [ ] Code follows project standards (manual verification required)',
    '- [ ] Self-review completed (manual verification required)',
    `- [${secretFindings.length ? ' ' : 'x'}] No obvious secrets or sensitive data in code`,
    '- [ ] Error handling implemented (manual verification required)',
    '- [ ] DRY principle followed (manual verification required)',
    '- [ ] Proper logging used (manual verification required)',
    '',
    '## Documentation',
    '- [ ] Code is properly commented (manual verification required)',
    '- [ ] README updated if applicable (manual verification required)',
    '- [ ] Function purpose documented (manual verification required)',
    '',
    '## Checklist',
    `- [${files.length ? 'x' : ' '}] All changed files listed`,
    `- [${secretFindings.length ? ' ' : 'x'}] No obvious secrets committed`,
    '- [ ] Dependencies pinned in requirements.txt (manual verification required)',
    `- [${hasTests ? 'x' : ' '}] Tests or rationale for no tests`,
    '- [ ] Docs/README updated if needed',
    '',
    '## Merge Risk Score',
    `**Risk Score: ${risk}/10**`,
    '',
    '**Risk drivers**:',
    ...(secretFindings.length ? ['- Secret-like additions detected by fallback scanner.'] : []),
    ...(failedChecks.length ? [`- ${failedChecks.length} CI check(s) not successful.`] : []),
    ...(!hasTests ? ['- No obvious test files changed.'] : []),
    `- AI review unavailable: ${error.message}`,
    '',
    '**Risk mitigations**:',
    '- Re-run after GitHub Models access is available for deeper semantic review.',
    '- Manually inspect each changed file before merge.',
    '',
    '## Merge Readiness',
    risk >= 7 ? 'Block. Fallback scanner detected high-risk conditions that require manual review.' : 'Needs follow-up items. AI review was unavailable, so manual verification is required before merge.',
    '',
    stage1 ? `Stage 1 review found from copilot-pull-request-reviewer[bot].` : 'MISSING - Stage 1 review not found.'
  ].join('\n');
}

function header({ pr }, risk) {
  return [
    `## Pre-Merge Review - Risk: ${risk}/10`,
    `> Execution Context: GITHUB ACTIONS | Review Mode: CODE`,
    '',
    `Repository: \`${repository}\`  Branch: \`${pr.head.ref}\` -> \`${pr.base.ref}\`  HEAD: \`${pr.head.sha.slice(0, 7)}\``
  ].join('\n');
}

function selectFiles(files) {
  const limit = files.length > 40 ? 25 : files.length;
  return [...files]
    .sort((a, b) => (b.changes || 0) - (a.changes || 0))
    .slice(0, limit);
}

function diffContext(files) {
  const selectedFiles = selectFiles(files);
  const sections = selectedFiles.map(file => [
    `FILE: ${file.filename}`,
    `STATUS: ${file.status} +${file.additions}/-${file.deletions}`,
    'PATCH:',
    truncate(file.patch || 'Patch unavailable (binary, renamed, or too large).', 10000)
  ].join('\n'));

  const skipped = files.length - selectedFiles.length;
  if (skipped > 0) {
    sections.push(`Large PR rule: ${skipped} file(s) omitted from prompt; review output must mark them as requiring manual per-file review.`);
  }

  return truncate(sections.join('\n\n---\n\n'), 65000);
}

function latestByUser(items, login) {
  return items
    .filter(item => item.user?.login === login)
    .sort((a, b) => new Date(b.submitted_at || b.created_at) - new Date(a.submitted_at || a.created_at))[0];
}

function checkSummary(checkRuns) {
  if (!checkRuns.length) {
    return '- MISSING - no check runs visible to this workflow.';
  }

  return checkRuns
    .map(check => `- ${check.name}: ${check.status}${check.conclusion ? ` / ${check.conclusion}` : ''}`)
    .join('\n');
}

function scanSecrets(files) {
  const findings = [];
  const patterns = [
    { reason: 'secret-like key assignment', regex: /^\+.*\b(api[_-]?key|secret|token|password|connection[_-]?string|accountkey)\b\s*[:=]/i },
    { reason: 'Azure/OpenAI key-shaped value', regex: /^\+.*\b(sk-[A-Za-z0-9_-]{12,}|[A-Za-z0-9+/]{40,}={0,2})\b/ },
    { reason: 'connection string fragment', regex: /^\+.*(DefaultEndpointsProtocol=|AccountKey=|Endpoint=sb:\/\/)/i }
  ];

  for (const file of files) {
    const patch = file.patch || '';
    for (const line of patch.split('\n')) {
      for (const pattern of patterns) {
        if (pattern.regex.test(line)) {
          findings.push({ file: file.filename, reason: pattern.reason });
          break;
        }
      }
    }
  }

  return findings;
}

function summarizePatchRisk(patch) {
  const lowered = patch.toLowerCase();
  const risks = [];

  if (/api[_-]?key|secret|token|password|accountkey/.test(lowered)) {
    risks.push('secret-like terms appear in the patch');
  }
  if (/except\s*:|except\s+exception/.test(patch)) {
    risks.push('broad exception handling may need review');
  }
  if (/requests\.(get|post|put|patch|delete)\(/.test(patch) && !/timeout\s*=/.test(patch)) {
    risks.push('HTTP call may need explicit timeout');
  }
  if (/json\(\)/.test(patch) && !/JSONDecodeError|ValueError/.test(patch)) {
    risks.push('JSON parsing error handling may need review');
  }

  return risks.length ? risks.join('; ') : 'No obvious fallback-scan issue detected.';
}

function calculateFallbackRisk(secretFindings, failedChecks, hasTests) {
  let risk = 3;
  if (!hasTests) risk += 2;
  if (failedChecks.length) risk += 2;
  if (secretFindings.length) risk = Math.max(risk + 3, 8);
  return Math.min(risk, 10);
}

function truncate(value, maxLength) {
  if (!value || value.length <= maxLength) {
    return value || '';
  }

  return `${value.slice(0, maxLength)}\n\n[TRUNCATED: ${value.length - maxLength} chars omitted]`;
}

async function upsertReviewComment(pr, review, issueComments) {
  const marker = `${markerPrefix} sha:${pr.head.sha} -->`;
  const body = `${marker}\n${review.trim()}\n`;

  const existing = issueComments
    .filter(comment => comment.body?.includes(markerPrefix) && comment.user?.login === 'github-actions[bot]')
    .sort((a, b) => new Date(b.created_at) - new Date(a.created_at))[0];

  if (existing) {
    await github(`/repos/${owner}/${repo}/issues/comments/${existing.id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ body })
    });
    console.log(`Updated pre-merge review comment ${existing.id}.`);
    return;
  }

  await github(`/repos/${owner}/${repo}/issues/${prNumber}/comments`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ body })
  });
  console.log(`Posted pre-merge review comment for PR #${prNumber}.`);
}