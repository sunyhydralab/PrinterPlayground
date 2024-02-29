// Initialize Scene, Camera, and Renderer
let scene = new THREE.Scene();
let camera = new THREE.PerspectiveCamera(75, window.innerWidth / window.innerHeight, 0.1, 1000);
camera.position.z = 5; // Initial z position of the camera

let renderer = new THREE.WebGLRenderer();
renderer.setSize(window.innerWidth, window.innerHeight);
document.body.appendChild(renderer.domElement);

let center = new THREE.Vector3(); // Initialize a vector for the center

async function fetchDataAndCreatePoints() {
    try {
        // Load the points from output.csv
        const response = await fetch('../output.csv');
        if (!response.ok) throw new Error('Network response was not ok.');

        const text = await response.text();
        const lines = text.split('\n');

        let parsedData = lines.map(line => {
            const columns = line.split(',');
            return columns.map(column => {
                const number = parseFloat(column.trim());
                if (isNaN(number)) {
                    console.error('Invalid number conversion', column);
                    return 0; // Provide a default value or handle appropriately
                }
                return number;
            });
        });

        // Filter out any invalid data points
        parsedData = parsedData.filter(item => item.length === 3 && !item.some(isNaN));

        if (parsedData.length === 0) {
            console.error("No valid data points found.");
            return;
        }

        // Define points using parsedData
        const points = parsedData.map(item => new THREE.Vector3(...item));

        // Create a geometry from the points
        const geometry = new THREE.BufferGeometry().setFromPoints(points);

        // Create a material for the points
        const material = new THREE.PointsMaterial({ color: 0xff0000, size: 0.1 });

        // Create points using the geometry and material
        const pointCloud = new THREE.Points(geometry, material);

        // Add the points to the scene
        scene.add(pointCloud);

        // Calculate the center of the point cloud and adjust camera
        calculateCenterAndAdjustCamera();

    } catch (error) {
        console.error("Failed to fetch and process the data:", error);
    }
}

function calculateCenterAndAdjustCamera() {
    let box = new THREE.Box3().setFromObject(scene);
    box.getCenter(center);
    let size = box.getSize(new THREE.Vector3());
    let maxDim = Math.max(size.x, size.y, size.z);
    let fov = camera.fov * (Math.PI / 180);
    let cameraZ = Math.abs(maxDim / 2 * Math.tan(fov * 2));
    
    // Adjust camera position to be centered and at a distance based on object size
    camera.position.set(center.x, center.y, center.z + cameraZ);
    
    // Manually adjust if necessary
    let manualOffset = new THREE.Vector3(50, 0, 0); // Adjust these values as needed
    camera.lookAt(center.add(manualOffset));

    // Render the scene
    renderer.render(scene, camera);
}

// Sync to GitHub

// Start the process
fetchDataAndCreatePoints();
