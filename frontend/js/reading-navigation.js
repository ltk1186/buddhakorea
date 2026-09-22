// A directly opened HTML file has no HTTP origin for the database-backed reader.
// Keep deployed links on their current host; file previews use the local reader host.
if (window.location.protocol === 'file:') {
    document.querySelectorAll('[data-reading-link]').forEach((link) => {
        link.href = 'http://127.0.0.1:8011/pali/';
    });
}
