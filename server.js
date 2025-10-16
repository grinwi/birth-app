const express = require('express');
const fs = require('fs');
const path = require('path');
const cors = require('cors');
const { exec } = require('child_process');

const app = express();
const PORT = process.env.PORT || 3000;
const DATA_PATH = path.join(__dirname, 'birthdays.csv');

// GitHub configuration for saving to repository
const GITHUB_REPO_OWNER = process.env.GITHUB_REPO_OWNER || 'grinwi';
const GITHUB_REPO = process.env.GITHUB_REPO || 'birth-app';
const GITHUB_BRANCH = process.env.GITHUB_BRANCH || 'main';
const GITHUB_FILE_PATH = process.env.GITHUB_FILE_PATH || 'birthdays.csv';
const GITHUB_API_BASE = 'https://api.github.com';

app.use(cors());
app.use(express.json());
app.use(express.text({ type: 'text/csv' }));

// Serve static files (frontend)
app.use(express.static(__dirname));

// API to GET current CSV
app.get('/csv', (req, res) => {
    fs.readFile(DATA_PATH, 'utf8', (err, data) => {
        if (err) {
            return res.status(404).send('CSV not found');
        }
        res.type('text/csv').send(data);
    });
});

// API to overwrite CSV
app.post('/csv', (req, res) => {
    const csv = req.body;
    if (typeof csv !== 'string' || csv.length < 10) {
        return res.status(400).send('Invalid or empty CSV');
    }
    fs.writeFile(DATA_PATH, csv, 'utf8', err => {
        if (err) return res.status(500).send('Failed to write CSV');
        res.send('CSV updated');
    });
});

/**
 * API to overwrite CSV on GitHub (commit to repo)
 * Requires:
 *   - env GITHUB_TOKEN with "repo" scope
 * Optional env overrides:
 *   - GITHUB_REPO_OWNER, GITHUB_REPO, GITHUB_BRANCH, GITHUB_FILE_PATH
 */
app.post('/csv/github', async (req, res) => {
    const token = process.env.GITHUB_TOKEN;
    if (!token) {
        return res.status(500).send('Server missing GITHUB_TOKEN environment variable.');
    }

    const csv = req.body;
    if (typeof csv !== 'string' || csv.length < 10) {
        return res.status(400).send('Invalid or empty CSV');
    }

    try {
        const fileUrl = `${GITHUB_API_BASE}/repos/${GITHUB_REPO_OWNER}/${GITHUB_REPO}/contents/${encodeURIComponent(GITHUB_FILE_PATH)}?ref=${encodeURIComponent(GITHUB_BRANCH)}`;
        const headers = {
            'Authorization': `Bearer ${token}`,
            'Accept': 'application/vnd.github+json',
            'User-Agent': 'birthdays-app-server'
        };

        // Fetch current file SHA (required by GitHub to update a file)
        const metaResp = await fetch(fileUrl, { headers });
        if (!metaResp.ok) {
            const t = await metaResp.text();
            return res.status(metaResp.status).send(`Failed to fetch file metadata from GitHub: ${t}`);
        }
        const metaJson = await metaResp.json();
        const currentSha = metaJson.sha;

        // Update file contents
        const putResp = await fetch(fileUrl, {
            method: 'PUT',
            headers: { ...headers, 'Content-Type': 'application/json' },
            body: JSON.stringify({
                message: 'Update birthdays.csv via app',
                content: Buffer.from(csv, 'utf8').toString('base64'),
                sha: currentSha,
                branch: GITHUB_BRANCH
            })
        });

        if (!putResp.ok) {
            const t = await putResp.text();
            return res.status(putResp.status).send(`Failed to update file on GitHub: ${t}`);
        }

        // Best-effort: also update local file
        fs.writeFile(DATA_PATH, csv, 'utf8', () => {});
        res.send('CSV pushed to GitHub');
    } catch (err) {
        console.error('GitHub update error:', err);
        res.status(500).send('GitHub update error');
    }
});

/**
 * API to overwrite CSV by committing with git and pushing to remote
 * Requires: the server process has git configured with write access to the remote.
 */
app.post('/csv/git', (req, res) => {
    const csv = req.body;
    if (typeof csv !== 'string' || csv.length < 10) {
        return res.status(400).send('Invalid or empty CSV');
    }
    fs.writeFile(DATA_PATH, csv, 'utf8', (err) => {
        if (err) return res.status(500).send('Failed to write CSV');
        // Stage, commit, and push
        exec('git add birthdays.csv && git commit -m "Update birthdays.csv via app" && git push', { cwd: __dirname }, (error, stdout, stderr) => {
            if (error) {
                console.error('Git push error:', stderr || error.message);
                return res.status(500).send('Git commit/push failed');
            }
            res.send('CSV committed and pushed via git');
        });
    });
});

app.listen(PORT, () => {
    console.log('Server listening on port', PORT);
});
