const GITHUB_CSV_URL = "https://raw.githubusercontent.com/grinwi/birth-app/main/birthdays.csv";
// Load CSV from GitHub on page load
window.addEventListener('DOMContentLoaded', () => {
    fetch(GITHUB_CSV_URL)
        .then(response => {
            if (!response.ok) throw new Error("Failed to load CSV from GitHub");
            return response.text();
        })
        .then(csvText => {
            const csvData = parseCSV(csvText);
            currentData = csvData;
            populateTable(csvData);
        })
        .catch(error => {
            console.error("Error loading CSV from GitHub:", error);
        });
});

document.getElementById('csv-file-input').addEventListener('change', handleFileInput);

let currentData = [];

let currentSort = [];

function sortData(sortType, button) {
    try {
        if (currentData.length === 0) return;

        // Check if the column is already being sorted
        let idx = currentSort.findIndex(sort => sort.type === sortType);
        if (idx !== -1) {
            // Toggle the order of the existing sort
            if (currentSort[idx].order === 'asc') {
                currentSort[idx].order = 'desc';
            } else if (currentSort[idx].order === 'desc') {
                // Going to neutral - remove from sorts
                currentSort.splice(idx, 1);
            } else {
                // In case neutral, pop out
                currentSort.splice(idx, 1);
            }
        } else {
            // Add a new sort in asc order
            currentSort.unshift({ type: sortType, order: 'asc' });
        }
        // If toggled to 'asc' or 'desc', bring it to the front
        idx = currentSort.findIndex(sort => sort.type === sortType);
        if (idx !== -1 && currentSort[idx].order) {
            const s = currentSort.splice(idx, 1)[0];
            currentSort.unshift(s);
        }

        // Update all sort buttons according to currentSort array
        const sortButtons = document.querySelectorAll('.sort-btn');
        sortButtons.forEach(btn => {
            const col = btn.id
                .replace('sort-', '')
                .replace('-btn', '')
                .replace(/-/g, '_');
            const found = currentSort.find(sort => sort.type === col);
            updateSortButton(btn, found ? found.order : '');
        });

        // Sort the data based on the current sort state
        currentData.sort((a, b) => {
            for (const sort of currentSort) {
                const result = sortByColumn(a, b, sort.type, sort.order);
                if (result !== 0) {
                    return result;
                }
            }
            return 0;
        });

        populateTable(currentData);
    } catch (error) {
        console.error('Error sorting data:', error);
    }
}

function sortByColumn(a, b, type, order) {
    switch (type) {
        case 'first_name':
            return order === 'asc' ? a.first_name.localeCompare(b.first_name) : order === 'desc' ? b.first_name.localeCompare(a.first_name) : 0;
        case 'last_name':
            return order === 'asc' ? a.last_name.localeCompare(b.last_name) : order === 'desc' ? b.last_name.localeCompare(a.last_name) : 0;
        case 'day':
            return order === 'asc' ? parseInt(a.day) - parseInt(b.day) : order === 'desc' ? parseInt(b.day) - parseInt(a.day) : 0;
        case 'month':
            return order === 'asc' ? parseInt(a.month) - parseInt(b.month) : order === 'desc' ? parseInt(b.month) - parseInt(a.month) : 0;
        case 'year':
            return order === 'asc' ? parseInt(a.year) - parseInt(b.year) : order === 'desc' ? parseInt(b.year) - parseInt(a.year) : 0;
        case 'age':
            const today = new Date();
            return order === 'asc' ? (today.getFullYear() - parseInt(a.year)) - (today.getFullYear() - parseInt(b.year)) : order === 'desc' ? (today.getFullYear() - parseInt(b.year)) - (today.getFullYear() - parseInt(a.year)) : 0;
        default:
            return 0;
    }
}


function handleFileInput(event) {
    const file = event.target.files[0];
    if (file) {
        const reader = new FileReader();
        reader.onload = () => {
            const csvData = parseCSV(reader.result);
            currentData = csvData;
            populateTable(csvData);

            // Reset all sort buttons to initial state
            const sortButtons = document.querySelectorAll('.sort-btn');
            sortButtons.forEach(btn => {
                btn.classList.remove('active-asc');
                btn.classList.remove('active-desc');
                const span = btn.querySelector('span');
                if (span) {
                    span.textContent = '↔';
                }
            });

            // Add event listeners for period filters (one shared function, update active state)
            const periodButtons = document.querySelectorAll('.period-btn');
            periodButtons.forEach(btn => {
                btn.addEventListener('click', function() {
                    periodButtons.forEach(b => b.classList.remove('active'));
                    btn.classList.add('active');
                    // Infer period value from id, 'all' for ALL
                    let period = btn.id.replace('-btn','').replace('all','all');
                    if (period === 'all') period = 'all';
                    else if (btn.id === 'today-btn') period = 'today';
                    else if (btn.id === 'this-week-btn') period = 'this-week';
                    else if (btn.id === 'next-week-btn') period = 'next-week';
                    else if (btn.id === 'this-month-btn') period = 'this-month';
                    else if (btn.id === 'next-month-btn') period = 'next-month';
                    else if (btn.id === 'this-quarter-btn') period = 'this-quarter';
                    else if (btn.id === 'next-quarter-btn') period = 'next-quarter';
                    else if (btn.id === 'this-year-btn') period = 'this-year';
                    else if (btn.id === 'next-year-btn') period = 'next-year';
                    applyActiveFilters(csvData, period);
                });
            });

            // Add event listener for modulo <select>
            document.getElementById('modulo-select').addEventListener('change', () => applyActiveFilters(csvData));

            // Add event listener for add row button
            document.getElementById('add-row-btn').addEventListener('click', () => {
                console.log('Add Row button clicked');
                addRow(csvData);
            });
        };
        reader.readAsText(file);
    }
}

function parseCSV(data) {
    try {
        const lines = data.trim().split('\n');
        const headers = lines.shift().split(',');
        return lines.map(line => {
            const values = line.split(',');
            return headers.reduce((obj, header, index) => {
                obj[header.trim().replace(/"/g, '')] = values[index].trim().replace(/"/g, '');
                return obj;
            }, {});
        });
    } catch (error) {
        console.error('Error parsing CSV data:', error);
        return [];
    }
}

let currentlyEditingRowIdx = null;
let rowBackup = null;

function populateTable(data) {
    try {
        const tbody = document.getElementById('birthdays-tbody');
        tbody.innerHTML = '';
        const today = new Date();
        const period = window.__activePeriod;
        const periodRange = period && period !== "all" ? getPeriodRange(period) : null;
        data.forEach((row, i) => {
            const tr = document.createElement('tr');

            // Editable row
            if (currentlyEditingRowIdx === i) {
                // Inputs for "first_name", "last_name", "day", "month", "year"
                ["first_name", "last_name", "day", "month", "year"].forEach(key => {
                    const td = document.createElement('td');
                    const inp = document.createElement('input');
                    inp.type = key === 'day' || key === 'month' || key === 'year' ? 'number' : 'text';
                    inp.value = row[key];
                    inp.min = key === 'day' ? 1 : (key === 'month' ? 1 : (key === 'year' ? 1900 : undefined));
                    inp.max = key === 'day' ? 31 : (key === 'month' ? 12 : undefined);
                    inp.style.width = '90%';
                    inp.id = `edit-input-${i}-${key}`;
                    td.appendChild(inp);
                    tr.appendChild(td);
                });
            } else {
                Object.keys(row).forEach(key => {
                    const td = document.createElement('td');
                    td.textContent = row[key];
                    tr.appendChild(td);
                });
            }

            // Age cell (readonly)
            const ageTd = document.createElement('td');
            let displayAge = today.getFullYear() - parseInt(row.year);
            const thisYearsBirthday = new Date(today.getFullYear(), parseInt(row.month)-1, parseInt(row.day));
            if (thisYearsBirthday > today) displayAge--;
            ageTd.textContent = displayAge;
            tr.appendChild(ageTd);

            // Next birthday col
            const nextBirthdayTd = document.createElement('td');
            let targetDate = today;
            if (periodRange && periodRange.end) {
                targetDate = periodRange.end;
            }
            let nY = targetDate.getFullYear();
            let nBDay = new Date(nY, parseInt(row.month)-1, parseInt(row.day));
            if (nBDay < targetDate) nBDay.setFullYear(nY+1);
            const nextBirthdayAge = nBDay.getFullYear() - parseInt(row.year);
            let birthdayInRange = null;
            if (periodRange && periodRange.start && periodRange.end) {
                let y = periodRange.start.getFullYear();
                let dt = new Date(y, parseInt(row.month)-1, parseInt(row.day));
                if (dt >= periodRange.start && dt <= periodRange.end) {
                    birthdayInRange = dt;
                } else {
                    y = periodRange.end.getFullYear();
                    dt = new Date(y, parseInt(row.month)-1, parseInt(row.day));
                    if (dt >= periodRange.start && dt <= periodRange.end) birthdayInRange = dt;
                }
            }
            let displayDate = "";
            if (birthdayInRange) {
                displayDate = `${birthdayInRange.getDate().toString().padStart(2, '0')}.${(birthdayInRange.getMonth()+1).toString().padStart(2, '0')}.${birthdayInRange.getFullYear()}`;
                nextBirthdayTd.textContent = `${birthdayInRange.getFullYear() - parseInt(row.year)} (${displayDate})`;
            } else {
                displayDate = `${nBDay.getDate().toString().padStart(2, '0')}.${(nBDay.getMonth()+1).toString().padStart(2, '0')}.${nBDay.getFullYear()}`;
                nextBirthdayTd.textContent = `${nextBirthdayAge} (${displayDate})`;
            }
            tr.appendChild(nextBirthdayTd);

            // Action buttons
            const actionsTd = document.createElement('td');
            if (currentlyEditingRowIdx === i) {
                const saveBtn = document.createElement('button');
                saveBtn.textContent = 'Save';
                saveBtn.classList.add('btn-save');
                saveBtn.onclick = () => saveRow(i);
                const cancelBtn = document.createElement('button');
                cancelBtn.textContent = 'Cancel';
                cancelBtn.classList.add('btn-cancel');
                cancelBtn.onclick = () => cancelEdit(i);
                actionsTd.appendChild(saveBtn);
                actionsTd.appendChild(cancelBtn);
            } else {
                // Always render Edit button visibly and first, with explicit properties.
                const editBtn = document.createElement('button');
                editBtn.innerText = 'Edit';
                editBtn.className = 'btn-edit'; // set class directly
                editBtn.style.display = 'inline-block'; // enforce visible
                editBtn.onclick = () => {
                    currentlyEditingRowIdx = i;
                    rowBackup = { ...row };
                    populateTable(data);
                };

                const deleteBtn = document.createElement('button');
                deleteBtn.innerText = 'Delete';
                deleteBtn.className = 'btn-delete'; // set class directly
                deleteBtn.style.display = 'inline-block';
                deleteBtn.onclick = () => {
                    deleteRow(row, data);
                };

                actionsTd.appendChild(editBtn);
                actionsTd.appendChild(deleteBtn);
            }
            tr.appendChild(actionsTd);
            tbody.appendChild(tr);
        });
    } catch (error) {
        console.error('Error populating table:', error);
    }
}

function saveRow(i) {
    // Save edited row values to currentData and leave edit mode
    if (currentlyEditingRowIdx !== i) return;
    const keys = ["first_name", "last_name", "day", "month", "year"];
    keys.forEach(key => {
        const inp = document.getElementById(`edit-input-${i}-${key}`);
        if (inp) {
            currentData[i][key] = inp.value;
        }
    });
    currentlyEditingRowIdx = null;
    rowBackup = null;
    populateTable(currentData);
}

function cancelEdit(i) {
    // Restore row from backup and leave edit mode
    if (currentlyEditingRowIdx !== i) return;
    if (rowBackup) {
        currentData[i] = { ...rowBackup };
    }
    currentlyEditingRowIdx = null;
    rowBackup = null;
    populateTable(currentData);
}

function filterData(data, filterType) {
    // This is kept for legacy/test buttons, but UI now uses applyActiveFilters.
    const period = filterType;
    applyActiveFilters(data, period);
}

// Helper: get start, end of this week (Sunday end), this/next month, quarters, etc.
function getPeriodRange(period) {
    const today = new Date();
    let start, end;
    switch (period) {
        case 'today':
            start = new Date(today); start.setHours(0,0,0,0);
            end = new Date(today); end.setHours(23,59,59,999);
            break;
        case 'this-week': {
            // From now to the coming Sunday
            start = new Date(today); start.setHours(0,0,0,0);
            end = new Date(today);
            end.setDate(end.getDate() + (7 - end.getDay()) % 7);
            end.setHours(23,59,59,999);
            break;
        }
        case 'next-week': {
            // Next calendar week: next Monday to next Sunday
            start = new Date(today);
            const daysToMonday = (8 - start.getDay()) % 7 || 7;
            start.setDate(start.getDate() + daysToMonday);
            start.setHours(0,0,0,0);
            end = new Date(start);
            end.setDate(start.getDate() + 6);
            end.setHours(23,59,59,999);
            break;
        }
        case 'this-month': {
            start = new Date(today.getFullYear(), today.getMonth(), 1, 0, 0, 0, 0);
            end = new Date(today.getFullYear(), today.getMonth() + 1, 0, 23, 59, 59, 999);
            break;
        }
        case 'next-month': {
            start = new Date(today.getFullYear(), today.getMonth() + 1, 1, 0, 0, 0, 0);
            end = new Date(today.getFullYear(), today.getMonth() + 2, 0, 23, 59, 59, 999);
            break;
        }
        case 'this-quarter': {
            const thisQ = Math.floor(today.getMonth()/3);
            start = new Date(today.getFullYear(), thisQ*3, 1, 0,0,0,0);
            end = new Date(today.getFullYear(), thisQ*3+3, 0, 23,59,59,999);
            break;
        }
        case 'next-quarter': {
            let nextQ = Math.floor(today.getMonth()/3)+1;
            let year = today.getFullYear();
            if (nextQ > 3) { nextQ = 0; year += 1; }
            start = new Date(year, nextQ*3, 1, 0,0,0,0);
            end = new Date(year, nextQ*3+3, 0, 23,59,59,999);
            break;
        }
        case 'this-year': {
            start = new Date(today.getFullYear(), 0, 1, 0,0,0,0);
            end = new Date(today.getFullYear(), 11, 31, 23,59,59,999);
            break;
        }
        case 'next-year': {
            start = new Date(today.getFullYear()+1, 0, 1, 0,0,0,0);
            end = new Date(today.getFullYear()+1, 11, 31, 23,59,59,999);
            break;
        }
        default:
            start = null; end = null;
    }
    return { start, end };
}

// Main function for layered filtering: called by both periods and when checkboxes are toggled
function applyActiveFilters(data, periodOverride) {
    // Determine selected period (by last period button click or last param)
    let period = periodOverride || window.__activePeriod;
    window.__activePeriod = period; // remember last period selected

    let filteredData = [...data];
    let periodRange = null;
    if (period && period !== 'all') {
        periodRange = getPeriodRange(period);
        if (periodRange.start && periodRange.end) {
            filteredData = filteredData.filter(row => {
                // Birthday in period: check if in [start, end] of period, birthdays repeat yearly
                let birthMonth = parseInt(row.month, 10);
                let birthDay = parseInt(row.day, 10);
                let birthDate = new Date(periodRange.start.getFullYear(), birthMonth - 1, birthDay);
                let candidateDates = [];
                // check for cases where period might span year boundary (like this quarter in Q4)
                let yearsToTry = [periodRange.start.getFullYear(), periodRange.end.getFullYear()];
                yearsToTry.forEach(yr => {
                    candidateDates.push(new Date(yr, birthMonth - 1, birthDay));
                });
                // At least one occurrence inside period counts as match.
                return candidateDates.some(cDate => (cDate >= periodRange.start && cDate <= periodRange.end));
            });
        }
    }

    // Modulo filter: single select (none, 5, or 10)
    const moduloSelect = document.getElementById('modulo-select');
    const moduloValue = moduloSelect ? moduloSelect.value : "none";
    if (moduloValue === "5" || moduloValue === "10") {
        const moduloNum = parseInt(moduloValue, 10);
        filteredData = filteredData.filter(row => {
            // Age "in period": birthday this period? Compute age as of birthday this period, else ignore
            let ageInPeriod = null;
            if (periodRange && periodRange.start) {
                // Find this person's birthday in the period, pick the closest after start
                let birthMonth = parseInt(row.month, 10);
                let birthDay = parseInt(row.day, 10);
                let year = periodRange.start.getFullYear();
                let bDate = new Date(year, birthMonth-1, birthDay);
                if (bDate < periodRange.start) bDate.setFullYear(year+1);
                if (bDate >= periodRange.start && bDate <= periodRange.end) {
                    ageInPeriod = bDate.getFullYear() - parseInt(row.year, 10);
                }
            } 
            // If no period is chosen, use age as of today (or this year if wanted)
            if (ageInPeriod === null) {
                const today = new Date();
                let bDate = new Date(today.getFullYear(), parseInt(row.month,10)-1, parseInt(row.day,10));
                ageInPeriod = today.getFullYear() - parseInt(row.year,10);
                if (bDate > today) ageInPeriod--; // hasn't had birthday yet
            }
            return ageInPeriod % moduloNum === 0;
        });
    }

    currentData = filteredData;
    populateTable(filteredData);
}

function getWeekNumber(date) {
    const firstDayOfYear = new Date(date.getFullYear(), 0, 1);
    const pastDaysOfYear = (date - firstDayOfYear) / 86400000;
    return Math.ceil((pastDaysOfYear + firstDayOfYear.getDay() + 1) / 7);
}

function addRow(data) {
    try {
        const newRow = {
            'first_name': prompt('Enter first name'),
            'last_name': prompt('Enter last name'),
            'day': prompt('Enter day'),
            'month': prompt('Enter month'),
            'year': prompt('Enter year')
        };
        data.push(newRow);
        currentData = data;
        populateTable(data);
    } catch (error) {
        console.error('Error adding row:', error);
    }
}

function editRow(row, data) {
    try {
        const index = data.indexOf(row);
        data[index]['first_name'] = prompt('Enter new first name', row['first_name']);
        data[index]['last_name'] = prompt('Enter new last name', row['last_name']);
        data[index]['day'] = prompt('Enter new day', row['day']);
        data[index]['month'] = prompt('Enter new month', row['month']);
        data[index]['year'] = prompt('Enter new year', row['year']);
        currentData = data;
        populateTable(data);
    } catch (error) {
        console.error('Error editing row:', error);
    }
}

function deleteRow(row, data) {
    try {
        const index = data.indexOf(row);
        data.splice(index, 1);
        currentData = data;
        populateTable(data);
    } catch (error) {
        console.error('Error deleting row:', error);
    }
}

function updateSortButton(button, order) {
    const span = button.querySelector('span');
    if (span) {
        switch (order) {
            case 'asc':
                span.textContent = '↑';
                button.classList.add('active-asc');
                button.classList.remove('active-desc');
                break;
            case 'desc':
                span.textContent = '↓';
                button.classList.remove('active-asc');
                button.classList.add('active-desc');
                break;
            default:
                span.textContent = '↔';
                button.classList.remove('active-asc');
                button.classList.remove('active-desc');
                break;
        }
    }
}

/* Save updated birthdays.csv to backend via POST */
function saveCSVToServer(data) {
    if (!data.length) {
        alert("No data to save.");
        return;
    }
    const keys = Object.keys(data[0]);
    const csvRows = [
        keys.join(','),
        ...data.map(row =>
            keys.map(field => `"${String(row[field]).replace(/"/g, '""')}"`).join(',')
        )
    ];
    const csvStr = csvRows.join('\n');

    fetch('/csv', {
        method: 'POST',
        headers: { 'Content-Type': 'text/csv' },
        body: csvStr
    }).then(res => {
        if (!res.ok) throw new Error('Failed to save CSV');
        alert('CSV saved successfully!');
    }).catch(() => {
        alert('Failed to save CSV to server.');
    });
}
