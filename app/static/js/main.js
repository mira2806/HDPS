// Theme Toggle
const themeToggleBtn = document.getElementById('theme-toggle-btn');
const htmlElement = document.documentElement;

// Initialize theme from localStorage or default to light
function initTheme() {
  const savedTheme = localStorage.getItem('theme') || 'light';
  htmlElement.setAttribute('data-theme', savedTheme);
}

// Toggle theme
function toggleTheme() {
  const currentTheme = htmlElement.getAttribute('data-theme');
  const newTheme = currentTheme === 'light' ? 'dark' : 'light';
  htmlElement.setAttribute('data-theme', newTheme);
  localStorage.setItem('theme', newTheme);
}

if (themeToggleBtn) {
  themeToggleBtn.addEventListener('click', toggleTheme);
}

// Initialize theme on page load
document.addEventListener('DOMContentLoaded', initTheme);

// Hamburger Menu Toggle
const hamburgerBtn = document.getElementById('hamburger-btn');
const navMenu = document.getElementById('nav-menu');

if (hamburgerBtn && navMenu) {
  hamburgerBtn.addEventListener('click', (e) => {
    e.stopPropagation();
    navMenu.classList.toggle('active');
  });

  // Close when any link or button inside nav-menu is clicked
  navMenu.querySelectorAll('.nav-link, .btn').forEach(el => {
    el.addEventListener('click', () => navMenu.classList.remove('active'));
  });

  // Close when clicking outside the navbar
  document.addEventListener('click', (e) => {
    if (!navMenu.contains(e.target) && !hamburgerBtn.contains(e.target)) {
      navMenu.classList.remove('active');
    }
  });
}

// Hero Carousel
const carouselSlides = document.querySelectorAll('.carousel-slide');
const carouselDots = document.querySelectorAll('.carousel-dots .dot');

if (carouselSlides.length > 0) {
  let currentSlide = 0;
  const totalSlides = carouselSlides.length;
  const autoAdvanceInterval = 3000; // 3 seconds

  function showSlide(n) {
    // Loop around
    if (n >= totalSlides) {
      currentSlide = 0;
    } else if (n < 0) {
      currentSlide = totalSlides - 1;
    } else {
      currentSlide = n;
    }

    // Update slide visibility
    carouselSlides.forEach(slide => slide.classList.remove('active'));
    carouselDots.forEach(dot => dot.classList.remove('active'));

    carouselSlides[currentSlide].classList.add('active');
    carouselDots[currentSlide].classList.add('active');
  }

  function nextSlide() {
    showSlide(currentSlide + 1);
  }

  // Auto-advance carousel
  const carouselInterval = setInterval(nextSlide, autoAdvanceInterval);

  // Manual dot navigation
  carouselDots.forEach((dot, index) => {
    dot.addEventListener('click', () => {
      showSlide(index);
      clearInterval(carouselInterval);
      setInterval(nextSlide, autoAdvanceInterval);
    });
  });

  // Touch swipe support
  let touchStartX = 0;
  const carouselEl = document.querySelector('.hero-carousel');
  if (carouselEl) {
    carouselEl.addEventListener('touchstart', (e) => {
      touchStartX = e.touches[0].clientX;
    }, { passive: true });
    carouselEl.addEventListener('touchend', (e) => {
      const diff = touchStartX - e.changedTouches[0].clientX;
      if (Math.abs(diff) > 50) {
        showSlide(diff > 0 ? currentSlide + 1 : currentSlide - 1);
      }
    }, { passive: true });
  }
}

// Back to Top Button
const backToTopBtn = document.getElementById('back-to-top-btn');

if (backToTopBtn) {
  // Show/hide button based on scroll position
  window.addEventListener('scroll', () => {
    if (window.pageYOffset > 300) {
      backToTopBtn.classList.add('show');
    } else {
      backToTopBtn.classList.remove('show');
    }
  });

  // Scroll to top smoothly
  backToTopBtn.addEventListener('click', () => {
    window.scrollTo({
      top: 0,
      behavior: 'smooth'
    });
  });
}

// Newsletter form is handled in index.html via AJAX
