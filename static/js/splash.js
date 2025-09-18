// splash.js
window.addEventListener('load', () => {
  setTimeout(() => {
    document.getElementById('splash').style.display = 'none';
    document.getElementById('main-navigation').classList.remove('hidden');
  }, 0000); // 5 seconds splash delay
});
