// script.js

// Get references to HTML elements
// Common display elements
const responseContainer = document.getElementById('responseContainer');
const errorDisplay = document.getElementById('errorDisplay');

// Table specific output elements
const tempOutput = document.getElementById('TempOutput');
const humidOutput = document.getElementById('HumidOutput');
const phOutput = document.getElementById('PHOutput');
const leafColorOutput = document.getElementById('LeafColor');
const trunkColorOutput = document.getElementById('TrunkColor');
const recommendationsOutput = document.getElementById('RecommendationsOutput'); 

// File Upload specific elements
const jsonFileUpload = document.getElementById('jsonFileUpload');
const uploadJsonBtn = document.getElementById('uploadJsonBtn');
const uploadSpinner = document.getElementById('uploadSpinner');
const fileUploadError = document.getElementById('fileUploadError');

// Load Last Saved (from server) specific elements (THESE ARE THE ONES WE'RE ADDING BACK!)
const loadSavedBtn = document.getElementById('loadSavedBtn');
const loadSavedSpinner = document.getElementById('loadSavedSpinner');


// Function to generate HTML for colors (as per your JSON structure)
function generateColorBoxes(colorData) {
    let html = '';
    // Ensure colorData is an object with seasons as keys
    if (typeof colorData !== 'object' || colorData === null) {
        return 'N/A'; // Or handle as an error
    }
    for (const season in colorData) {
        if (Object.hasOwnProperty.call(colorData, season) && Array.isArray(colorData[season])) {
            html += `<strong>${season}:</strong> `;
            colorData[season].forEach(color => {
                html += `<span class="color-box" style="background-color: ${color};"></span>`;
            });
            html += '<br>'; // New line for each season
        }
    }
    return html;
}

// Function to display data in the HTML table
function displayRecommendations(data) {
    if (!data) {
        // Clear all output fields if no data
        tempOutput.innerHTML = '...';
        humidOutput.innerHTML = '...';
        phOutput.innerHTML = '...';
        leafColorOutput.innerHTML = '...';
        trunkColorOutput.innerHTML = '...';
        recommendationsOutput.innerHTML = '...';

        errorDisplay.textContent = 'No data to display.';
        errorDisplay.classList.remove('hidden');
        responseContainer.classList.remove('hidden'); // Ensure container is visible
        return;
    }

    // Populate table cells with data, use 'N/A' if data is missing
    tempOutput.innerHTML = data.Temp || 'N/A';
    humidOutput.innerHTML = data.Humidity || 'N/A';
    phOutput.innerHTML = data['Soil PH'] || 'N/A';
    recommendationsOutput.innerHTML = data.Recommendations || 'N/A';

    // Handle Leaf color
    if (data['Leaf color']) {
        leafColorOutput.innerHTML = generateColorBoxes(data['Leaf color']);
    } else {
        leafColorOutput.innerHTML = 'N/A';
    }

    // Handle Trunk color
    if (data['Trunk color']) {
        trunkColorOutput.innerHTML = generateColorBoxes(data['Trunk color']);
    } else {
        trunkColorOutput.innerHTML = 'N/A';
    }

    responseContainer.classList.remove('hidden'); // Ensure the container holding the table is visible
    errorDisplay.classList.add('hidden'); // Hide any previous errors
    fileUploadError.classList.add('hidden'); // Also clear file upload errors
}

// Function to handle showing/hiding spinners and disabling buttons
function setLoadingState(spinnerEl, buttonEl) {
    // Clear previous results
    tempOutput.innerHTML = '...';
    humidOutput.innerHTML = '...';
    phOutput.innerHTML = '...';
    leafColorOutput.innerHTML = '...';
    trunkColorOutput.innerHTML = '...';
    recommendationsOutput.innerHTML = '...';

    errorDisplay.textContent = '';
    fileUploadError.textContent = '';
    errorDisplay.classList.add('hidden');
    fileUploadError.classList.add('hidden');
    
    // Hide the results container until data is ready
    responseContainer.classList.add('hidden'); 
    
    if (spinnerEl) spinnerEl.style.display = 'inline-block';
    if (buttonEl) buttonEl.disabled = true;
    
    // Disable other related buttons if they exist
    // Check if buttons exist before disabling
    if (uploadJsonBtn) uploadJsonBtn.disabled = true;
    if (loadSavedBtn) loadSavedBtn.disabled = true;

    // Re-enable the specific button that triggered the load, this is handled in finally block
    // No need to exclude here, as it will be re-enabled later.
}

function resetLoadingState(spinnerEl, buttonEl) {
    if (spinnerEl) spinnerEl.style.display = 'none';
    if (buttonEl) buttonEl.disabled = false;

    // Re-enable other related buttons if they exist
    if (uploadJsonBtn) uploadJsonBtn.disabled = false;
    if (loadSavedBtn) loadSavedBtn.disabled = false;
}


// ----- FILE UPLOAD LOGIC -----
uploadJsonBtn.addEventListener('click', () => {
    const file = jsonFileUpload.files[0]; // Get the selected file

    if (!file) {
        fileUploadError.textContent = 'Please select a JSON file to upload.';
        fileUploadError.classList.remove('hidden');
        return;
    }

    if (file.type !== 'application/json') {
        fileUploadError.textContent = 'Invalid file type. Please select a .json file.';
        fileUploadError.classList.remove('hidden');
        return;
    }

    setLoadingState(uploadSpinner, uploadJsonBtn); // Set loading state for upload

    const reader = new FileReader(); // Create a FileReader object

    reader.onload = (e) => { // This function runs when the file is successfully read
        try {
            const jsonString = e.target.result; // The file content as a string
            const dataObject = JSON.parse(jsonString); // Parse the string into a JS object
            displayRecommendations(dataObject); // Display the data
            fileUploadError.classList.add('hidden'); // Hide any file upload errors
        } catch (parseError) {
            console.error("Error parsing JSON file:", parseError);
            fileUploadError.textContent = `Error parsing JSON file: ${parseError.message}`;
            fileUploadError.classList.remove('hidden');
            // Ensure container visible to show error
            responseContainer.classList.remove('hidden'); 
        } finally {
            resetLoadingState(uploadSpinner, uploadJsonBtn); // Reset loading state
        }
    };

    reader.onerror = () => { // This function runs if there's an error reading the file
        console.error("Error reading file:", reader.error);
        fileUploadError.textContent = `Error reading file: ${reader.error.message}`;
        fileUploadError.classList.remove('hidden');
        // Ensure container visible to show error
        responseContainer.classList.remove('hidden'); 
        resetLoadingState(uploadSpinner, uploadJsonBtn); // Reset loading state
    };

    reader.readAsText(file); // Start reading the file as text
});


// ----- LOAD LAST SAVED (from server) LOGIC (Optional, keep if you want this button) -----
// Check if the button exists in HTML before adding event listener (This check is good practice)
if (loadSavedBtn) { 
    loadSavedBtn.addEventListener('click', async () => {
        setLoadingState(loadSavedSpinner, loadSavedBtn);

        try {
            const response = await fetch('./SavedRec.json'); 
            
            if (!response.ok) {
                if (response.status === 404) {
                    throw new Error('SavedRec.json not found. Please ensure it exists in the same directory as index.html.');
                } else {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
            }
            
            const dataObject = await response.json(); 
            displayRecommendations(dataObject);
            
        } catch (error) {
            console.error('Error loading SavedRec.json:', error);
            errorDisplay.textContent = `Error loading saved data: ${error.message}`;
            errorDisplay.classList.remove('hidden');
            responseContainer.classList.remove('hidden');
        } finally {
            resetLoadingState(loadSavedSpinner, loadSavedBtn);
        }
    });
}
