const express = require('express');
const fs = require('fs');
const path = require('path');
const cors = require('cors');

const app = express();
const PORT = process.env.PORT || 3000;
const DATA_PATH = path.join(__dirname, 'birthdays.csv');

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

app.listen(PORT, () => {
    console.log('Server listening on port', PORT);
});
