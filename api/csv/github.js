/**
 * Vercel serverless function that:
 *  - Creates a new branch off base (default: main)
 *  - Commits the posted birthdays.csv to that branch
 *  - Opens a Pull Request back to base
 *
 * Env vars (set in Vercel Project Settings -> Environment Variables):
 *   REQUIRED:
 *     - GITHUB_APP_ID
 *     - GITHUB_APP_INSTALLATION_ID
 *     - GITHUB_APP_PRIVATE_KEY  (full PEM string inc. BEGIN/END, with newlines)
 *   OPTIONAL (defaults shown):
 *     - GITHUB_REPO_OWNER=grinwi
 *     - GITHUB_REPO=birth-app
 *     - GITHUB_BRANCH=main
 *     - GITHUB_FILE_PATH=birthdays.csv
 *     - PR_BRANCH_PREFIX=update-birthdays
 *
 * Request:
 *   POST text/csv body (raw CSV)
 *
 * Response:
 *   200 JSON { pr_url, pr_number, branch } on success
 */
const { App } = require('@octokit/app');

function setCors(res) {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');
}

module.exports = async (req, res) => {
  setCors(res);

  if (req.method === 'OPTIONS') {
    return res.status(204).end();
  }
  if (req.method !== 'POST') {
    return res.status(405).send('Method Not Allowed');
  }

  try {
    const csv = await readRawBody(req);
    if (!csv || typeof csv !== 'string' || csv.length < 10) {
      return res.status(400).send('Invalid or empty CSV');
    }

    const owner = process.env.GITHUB_REPO_OWNER || 'grinwi';
    const repo = process.env.GITHUB_REPO || 'birth-app';
    const baseBranch = process.env.GITHUB_BRANCH || 'main';
    const filePath = process.env.GITHUB_FILE_PATH || 'birthdays.csv';
    const prBranchPrefix = (process.env.PR_BRANCH_PREFIX || 'update-birthdays').replace(/[^a-zA-Z0-9._/-]/g, '-') || 'update-birthdays';

    const appId = process.env.GITHUB_APP_ID;
    const installationId = process.env.GITHUB_APP_INSTALLATION_ID;
    const privateKey = process.env.GITHUB_APP_PRIVATE_KEY;

    if (!appId || !installationId || !privateKey) {
      return res.status(500).send('Server missing GITHUB_APP_ID / GITHUB_APP_INSTALLATION_ID / GITHUB_APP_PRIVATE_KEY');
    }

    const app = new App({ appId, privateKey });
    const octokit = await app.getInstallationOctokit(Number(installationId));

    const apiHeaders = { 'X-GitHub-Api-Version': '2022-11-28' };

    // 1) Resolve base branch HEAD sha
    const baseRef = await octokit.request('GET /repos/{owner}/{repo}/git/ref/{ref}', {
      owner,
      repo,
      ref: `heads/${baseBranch}`,
      headers: apiHeaders
    });
    const baseSha = baseRef.data.object && baseRef.data.object.sha;
    if (!baseSha) {
      return res.status(500).send('Failed to resolve base branch HEAD SHA');
    }

    // 2) Create a unique PR branch off base
    let prBranch = buildBranchName(prBranchPrefix);
    prBranch = await ensureNewBranch(octokit, owner, repo, prBranch, baseSha, apiHeaders);

    // 3) Determine current file sha on the new branch (if file exists there)
    let currentSha = null;
    try {
      const meta = await octokit.request('GET /repos/{owner}/{repo}/contents/{path}', {
        owner, repo, path: filePath, ref: prBranch, headers: apiHeaders
      });
      currentSha = meta.data.sha;
    } catch (e) {
      // 404 means the file doesn't exist on that branch, that's fine
      if (!e || e.status !== 404) throw e;
    }

    // 4) Commit file content on PR branch
    const contentB64 = Buffer.from(csv, 'utf8').toString('base64');
    await octokit.request('PUT /repos/{owner}/{repo}/contents/{path}', {
      owner,
      repo,
      path: filePath,
      message: 'Update birthdays.csv via GitHub App backend (PR)',
      content: contentB64,
      sha: currentSha || undefined,
      branch: prBranch,
      headers: apiHeaders
    });

    // 5) Open PR from PR branch into base
    const prTitle = 'Update birthdays.csv';
    const prBody = 'Automated update of birthdays.csv via the Birth App backend.';
    const pr = await octokit.request('POST /repos/{owner}/{repo}/pulls', {
      owner,
      repo,
      title: prTitle,
      head: prBranch,
      base: baseBranch,
      body: prBody,
      headers: apiHeaders
    });

    return res.status(200).json({
      pr_url: pr.data && pr.data.html_url,
      pr_number: pr.data && pr.data.number,
      branch: prBranch
    });
  } catch (err) {
    console.error('GitHub App PR flow error:', err);
    return res.status(500).send('GitHub App PR flow error');
  }
};

function readRawBody(req) {
  return new Promise((resolve, reject) => {
    let body = '';
    req.on('data', (chunk) => (body += chunk));
    req.on('end', () => resolve(body));
    req.on('error', reject);
  });
}

function buildBranchName(prefix) {
  const stamp = new Date().toISOString().replace(/[-:TZ]/g, '').slice(0, 14);
  return `${prefix}-${stamp}`;
}

async function ensureNewBranch(octokit, owner, repo, name, baseSha, headers) {
  let branchName = name;
  let attempt = 0;
  while (true) {
    try {
      await octokit.request('POST /repos/{owner}/{repo}/git/refs', {
        owner,
        repo,
        ref: `refs/heads/${branchName}`,
        sha: baseSha,
        headers
      });
      return branchName;
    } catch (e) {
      // 422 Unprocessable Entity if ref already exists
      if (e && e.status === 422 && attempt < 5) {
        attempt += 1;
        const rand = Math.random().toString(36).slice(2, 8);
        branchName = `${name}-${rand}`;
        continue;
      }
      throw e;
    }
  }
}
