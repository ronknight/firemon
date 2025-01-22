function updateMapCenter() {
    fetch('/get_map_center')
        .then(response => response.json())
        .then(data => {
            const mapCenter = data.map_center;
            map.setView(mapCenter, 13); // Update the map view with the new center
        })
        .catch(error => console.error('Error fetching map center:', error));
}

function changeLocation(newCenter) {
    fetch('/update_map_center', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ map_center: newCenter })
    })
    .then(response => response.json())
    .then(data => {
        if (data.status === 'success') {
            updateMapCenter(); // Update the map center after changing location
        }
    })
    .catch(error => console.error('Error updating map center:', error));
}

// Call updateMapCenter when needed, e.g., on page load or when location changes
updateMapCenter();

// Example usage: changeLocation([37.7749, -122.4194]); // Change to San Francisco