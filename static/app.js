(() => {
  'use strict';
  const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  document.documentElement.classList.add('js-ready');
  // Play the opening curtain on the first visit in this tab, not on every refresh.
  try {
    if (sessionStorage.getItem('officeOscarsCurtainSeen') === 'yes') {
      document.documentElement.classList.add('intro-seen');
    } else {
      sessionStorage.setItem('officeOscarsCurtainSeen', 'yes');
    }
  } catch (_) { /* Private mode can block storage; visual experience still works. */ }


  // Reveal content, but never hide it when animations are disabled or unsupported.
  const reveals = document.querySelectorAll('.reveal');
  if ('IntersectionObserver' in window && !reducedMotion) {
    const observer = new IntersectionObserver((entries, obs) => {
      for (const entry of entries) if (entry.isIntersecting) {
        entry.target.classList.add('is-visible');
        obs.unobserve(entry.target);
      }
    }, { threshold: .09, rootMargin: '0px 0px -12px 0px' });
    reveals.forEach(item => observer.observe(item));
    // Ensure content from the initially visible viewport is not obscured by unusual observer timing.
    setTimeout(() => reveals.forEach(item => {
      if (item.getBoundingClientRect().top < window.innerHeight * .95) item.classList.add('is-visible');
    }), 80);
  } else reveals.forEach(item => item.classList.add('is-visible'));

  document.querySelectorAll('.lookbook-card img').forEach(img => {
    img.addEventListener('error', () => img.classList.add('image-unavailable'));
    if (img.complete && img.naturalWidth === 0) img.classList.add('image-unavailable');
  });

  const progress = document.querySelector('#readingProgress');
  const mobileRsvp = document.querySelector('.mobile-rsvp');
  const rsvpSection = document.querySelector('#rsvp');
  const heroSection = document.querySelector('#top');
  const footerSection = document.querySelector('.site-footer');
  const siteHeader = document.querySelector('#siteHeader');

  let scrollScheduled = false;
  function onScroll() {
    scrollScheduled = false;
    const max = Math.max(1, document.documentElement.scrollHeight - innerHeight);
    progress.style.width = `${Math.min(100, Math.max(0, scrollY / max * 100))}%`;
    if (siteHeader) siteHeader.classList.toggle('is-scrolled', scrollY > 32);
    if (mobileRsvp && rsvpSection && heroSection) {
      const bounds = rsvpSection.getBoundingClientRect();
      const heroBounds = heroSection.getBoundingClientRect();
      const footerBounds = footerSection ? footerSection.getBoundingClientRect() : null;
      const atForm = bounds.top < innerHeight * .75 && bounds.bottom > 65;
      const atFooter = footerBounds && footerBounds.top < innerHeight * .9;
      const pastHero = heroBounds.bottom < innerHeight * .57;
      mobileRsvp.classList.toggle('is-active', pastHero && !atForm && !atFooter);
      mobileRsvp.classList.toggle('is-hidden', !pastHero || atForm || atFooter);
    }
  }
  window.addEventListener('scroll', () => {
    if (!scrollScheduled) { scrollScheduled = true; requestAnimationFrame(onScroll); }
  }, { passive: true });
  onScroll();
  window.addEventListener('resize', onScroll, { passive: true });

  // Event starts 2026-12-26 at 18:00 in Moscow (UTC+3): 15:00 UTC.
  const eventTime = Date.parse('2026-12-26T18:00:00+03:00');
  const timer = document.getElementById('countdownTimer');
  const finished = document.getElementById('countdownFinished');
  const timeNodes = ['days', 'hours', 'minutes', 'seconds'].map(id => document.getElementById(id));
  function updateCountdown() {
    const remaining = Math.max(0, eventTime - Date.now());
    if (!remaining) {
      timer.hidden = true;
      finished.hidden = false;
      return true;
    }
    timer.hidden = false;
    finished.hidden = true;
    const sec = Math.floor(remaining / 1000);
    const values = [Math.floor(sec / 86400), Math.floor(sec / 3600) % 24, Math.floor(sec / 60) % 60, sec % 60];
    values.forEach((num, index) => { timeNodes[index].textContent = String(num).padStart(2, '0'); });
    return false;
  }
  if (!updateCountdown()) {
    const interval = setInterval(() => { if (updateCountdown()) clearInterval(interval); }, 1000);
  }

  // Gentle ambient confetti at the end. Decorative, disabled when reduced motion is preferred.
  if (!reducedMotion) {
    const finalConfetti = document.getElementById('finalConfetti');
    for (let i = 0; i < 33; i++) {
      const item = document.createElement('i');
      item.className = 'falling-piece';
      item.style.setProperty('--left', `${(i * 37.7) % 100}%`);
      item.style.setProperty('--size', `${2 + (i % 3) * 2}px`);
      item.style.setProperty('--rotation', `${i * 73}deg`);
      item.style.setProperty('--duration', `${13 + i % 13}s`);
      item.style.setProperty('--delay', `${-i * .85}s`);
      item.style.setProperty('--drift', `${(i % 2 ? 1 : -1) * (20 + i % 50)}px`);
      item.style.setProperty('--brightness', `${.65 + (i % 4) / 8}`);
      finalConfetti.appendChild(item);
    }
  }


  // Minimal, keyboard-accessible mobile navigation.
  const menuToggle = document.getElementById('menuToggle');
  const menu = document.getElementById('mobileMenu');
  function setMenu(open) {
    if (!menu || !menuToggle) return;
    menu.hidden = !open;
    menuToggle.setAttribute('aria-expanded', String(open));
    menuToggle.setAttribute('aria-label', open ? 'Закрыть меню' : 'Открыть меню');
    document.body.classList.toggle('menu-open', open);
    if (open) menu.querySelector('a')?.focus();
  }
  menuToggle?.addEventListener('click', () => setMenu(menu.hidden));
  menu?.querySelectorAll('a').forEach(link => link.addEventListener('click', () => setMenu(false)));
  document.addEventListener('keydown', event => {
    if (event.key === 'Escape' && menu && !menu.hidden) {
      setMenu(false);
      menuToggle?.focus();
    }
  });
  window.matchMedia('(min-width: 761px)').addEventListener('change', event => {
    if (event.matches) setMenu(false);
  });

  // A small tactile surprise for phone users: still no spoilers revealed.
  const envelope = document.getElementById('secretEnvelope');
  envelope?.addEventListener('click', () => {
    const open = envelope.classList.toggle('is-open');
    envelope.setAttribute('aria-pressed', String(open));
  });

  const form = document.getElementById('rsvpForm');
  const submitButton = document.getElementById('submitButton');
  const fullName = document.getElementById('fullName');
  const department = document.getElementById('department');
  const formError = document.getElementById('formError');
  const yesNo = [...form.querySelectorAll('input[name="attendance"]')];
  let currentKey = null;
  let isSubmitting = false;

  function setError(id, message) { document.getElementById(id).textContent = message || ''; }
  function validate() {
    const name = fullName.value.trim().replace(/\s+/g, ' ');
    const dept = department.value.trim().replace(/\s+/g, ' ');
    const option = yesNo.find(input => input.checked);
    const isNameValid = name.length >= 3 && name.split(/\s+/).length >= 2;
    const isDeptValid = dept.length >= 2;
    setError('nameError', isNameValid ? '' : 'Укажите имя и фамилию.');
    setError('departmentError', isDeptValid ? '' : 'Укажите ваш отдел или команду.');
    setError('attendanceError', option ? '' : 'Пожалуйста, выберите один вариант.');
    fullName.setAttribute('aria-invalid', String(!isNameValid));
    department.setAttribute('aria-invalid', String(!isDeptValid));
    if (!isNameValid) fullName.focus();
    else if (!isDeptValid) department.focus();
    else if (!option) yesNo[0].focus();
    return isNameValid && isDeptValid && Boolean(option);
  }
  [fullName, department, ...yesNo].forEach(el => el.addEventListener('input', () => {
    formError.hidden = true;
    setError('nameError', '');setError('departmentError', '');setError('attendanceError', '');
    el.removeAttribute('aria-invalid');
    // Editing after an unsuccessful attempt represents a new response.
    currentKey = null;
  }));

  function celebrate() {
    if (reducedMotion) return;
    const layer = document.getElementById('confettiLayer');
    for (let i = 0; i < 70; i++) {
      const p = document.createElement('i');
      p.className = 'celebrate-piece';
      p.style.setProperty('--left', `${Math.random() * 100}%`);
      p.style.setProperty('--size', `${3 + Math.random() * 6}px`);
      p.style.setProperty('--rotation', `${Math.random() * 360}deg`);
      p.style.setProperty('--duration', `${2.6 + Math.random() * 2.5}s`);
      p.style.setProperty('--delay', `${Math.random() * .7}s`);
      p.style.setProperty('--drift', `${-140 + Math.random() * 280}px`);
      p.style.setProperty('--color', ['#d4af37','#f5e6c8','#aa7e32','#fcdf8c'][i % 4]);
      layer.appendChild(p);
      p.addEventListener('animationend', () => p.remove(), { once: true });
    }
  }

  form.addEventListener('submit', async event => {
    event.preventDefault();
    if (isSubmitting || !validate()) return;
    isSubmitting = true;
    formError.hidden = true;
    currentKey ||= (crypto.randomUUID ? crypto.randomUUID() : `${Date.now()}-${Math.random().toString(36).slice(2)}`);
    const previousText = submitButton.firstElementChild.textContent;
    submitButton.disabled = true;
    submitButton.firstElementChild.textContent = 'Отправляем…';
    const attendance = yesNo.find(input => input.checked).value;
    const payload = {fullName: fullName.value.trim().replace(/\s+/g,' '), department: department.value.trim().replace(/\s+/g,' '), attendance, requestId: currentKey};
    try {
      const response = await fetch('/api/rsvp', { method: 'POST', headers: {'Content-Type': 'application/json'}, credentials: 'same-origin', body: JSON.stringify(payload), signal: AbortSignal.timeout(15000) });
      let result;
      try { result = await response.json(); } catch { throw new Error('Сервер прислал некорректный ответ. Попробуйте ещё раз.'); }
      if (!response.ok || !result.saved) throw new Error(result.error || 'Не удалось сохранить ответ. Попробуйте ещё раз.');
      const affirmative = attendance === 'yes';
      document.getElementById('successTitle').textContent = affirmative ? 'Your name is on the list!' : 'Спасибо, что сообщили!';
      document.getElementById('successMessage').textContent = affirmative ? 'Ваше присутствие подтверждено. Готовьте праздничный образ — увидимся на красной дорожке!' : 'Будем скучать по вам на нашей премьере.';
      document.getElementById('formStage').hidden = true;
      const success = document.getElementById('successStage');
      success.hidden = false;
      success.focus();
      if (affirmative) celebrate();
    } catch (err) {
      formError.textContent = err instanceof TypeError ? 'Не удалось связаться с сервером. Проверьте интернет и попробуйте ещё раз.' : err.message;
      formError.hidden = false;
      // Keep the same idempotency key for a retry after a network/server error.
    } finally {
      isSubmitting = false;
      submitButton.disabled = false;
      submitButton.firstElementChild.textContent = previousText;
    }
  });
})();
