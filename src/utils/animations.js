// Simplified animation utilities
document.addEventListener("astro:page-load", () => {
  const fadeUpElements = document.querySelectorAll('.fade-up');
  if (fadeUpElements.length > 0) {
    const observer = new IntersectionObserver((entries) => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          entry.target.classList.add('visible');
          observer.unobserve(entry.target);
        }
      });
    }, { threshold: 0.1 });
    fadeUpElements.forEach(el => observer.observe(el));
  }
  
  const animateLists = document.querySelectorAll('ul.animate-list');
  if (animateLists.length > 0) {
    animateLists.forEach(list => {
      list.querySelectorAll('li').forEach(item => {
        item.classList.add('animate-list-item');
      });
    });
  }
});
