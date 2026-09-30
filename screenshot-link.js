const express = require('express');
const axios = require('axios');
const { execSync } = require('child_process');
const fs = require('fs');
const path = require('path');
const os = require('os');

const app = express();
const PORT = 5000;
const OUTPUT_DIR = path.join(__dirname, 'screenshot_tmp');

// Ensure output directory exists
if (!fs.existsSync(OUTPUT_DIR)) {
    fs.mkdirSync(OUTPUT_DIR);
}

/**
 * Capture the screen using Termux:API
 * @returns {string} Path to the local screenshot file
 */
function captureScreen() {
    const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
    const filename = `shot_${timestamp}.png`;
    const filepath = path.join(OUTPUT_DIR, filename);

    try {
        // Execute termux-screenshot command
        execSync(`termux-screenshot -f "${filepath}"`, { stdio: 'inherit' });
        
        // Verify file was created
        if (fs.existsSync(filepath)) {
            return filepath;
        } else {
            throw new Error('Screenshot file not found after capture.');
        }
    } catch (error) {
        console.error('Capture failed:', error.message);
        throw error;
    }
}

/**
 * Upload a file to a public paste service (0x0.st)
 * @param {string} filepath - Local path to the file
 * @returns {Promise<string>} The public URL of the uploaded file
 */
async function uploadToPublicHost(filepath) {
    const form = new FormData();
    const fileStream = fs.createReadStream(filepath);
    form.append('file', fileStream);

    try {
        const response = await axios.post('https://0x0.st', form, {
            headers: form.getHeaders(),
            maxContentLength: Infinity,
            maxBodyLength: Infinity
        });
        return response.data.trim();
    } catch (error) {
        console.error('Upload failed:', error.message);
        throw error;
    }
}

// Route: Trigger Capture and Redirect
app.get('/', async (req, res) => {
    console.log(`[!] Request received from ${req.ip} at ${new Date().toISOString()}`);
    
    try {
        // 1. Capture the screen
        const localPath = captureScreen();
        
        // 2. Upload to public host
        const publicUrl = await uploadToPublicHost(localPath);
        
        // 3. Clean up local file
        fs.unlinkSync(localPath);
        
        // 4. Redirect user to the public URL
        console.log(`[+] Redirecting to: ${publicUrl}`);
        res.redirect(publicUrl);

    } catch (error) {
        res.status(500).send(`Error: ${error.message}`);
    }
});

// Start Server
app.listen(PORT, '0.0.0.0', () => {
    console.log(`[+] Screenshot Server running on http://0.0.0.0:${PORT}`);
    console.log(`[+] Open http://<127.0.0.1>:${PORT} to trigger a capture.`);
});
