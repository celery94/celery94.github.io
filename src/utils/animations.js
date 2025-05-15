// Animation utilities for enhanced user experience

document.addEventListener("astro:page-load", () => {
  // Setup scroll animations with IntersectionObserver
  const fadeUpElements = document.querySelectorAll('.fade-up');
  
  if (fadeUpElements.length > 0) {
    const fadeUpObserver = new IntersectionObserver((entries) => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          entry.target.classList.add('visible');
          fadeUpObserver.unobserve(entry.target);
        }
      });
    }, {
      threshold: 0.1
    });
    
    fadeUpElements.forEach(element => {
      fadeUpObserver.observe(element);
    });
  }
  
  // Add ripple effect to ripple-button elements
  const rippleButtons = document.querySelectorAll('.ripple-button');
  
  if (rippleButtons.length > 0) {
    rippleButtons.forEach(button => {
      button.addEventListener('click', function(e) {
        const x = e.clientX - button.getBoundingClientRect().left;
        const y = e.clientY - button.getBoundingClientRect().top;
        
        const ripple = document.createElement('span');
        ripple.classList.add('ripple');
        ripple.style.left = x + 'px';
        ripple.style.top = y + 'px';
        
        this.appendChild(ripple);
        
        setTimeout(() => {
          ripple.remove();
        }, 600);
      });
    });
  }
  
  // Add animation class to list items for staggered entrance
  const animateLists = document.querySelectorAll('ul.animate-list');
  
  if (animateLists.length > 0) {
    animateLists.forEach(list => {
      list.querySelectorAll('li').forEach(item => {
        item.classList.add('animate-list-item');
      });
    });
  }
});
