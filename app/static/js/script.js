// Initialiser Particles.js
particlesJS.load('particles-js', '/static/css/particles.json', function() {
    console.log('Particles.js chargé');
});

var map = L.map('map').setView([12.372365, -1.628863], 6); // Coordonnées du Burkina Faso
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 18,
}).addTo(map);

// Ajouter un marqueur pour un exemple
L.marker([12.372365, -1.628863]).addTo(map)
    .bindPopup("Exemple de zone agricole.")
    .openPopup();