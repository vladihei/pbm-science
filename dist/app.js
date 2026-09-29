(function () {
  const toggle = document.querySelector('.nav-toggle');
  const nav = document.querySelector('.site-nav');
  if (nav && !nav.querySelector('a[href="/articles/"]')) {
    const articlesLink = document.createElement('a');
    articlesLink.href = '/articles/';
    articlesLink.textContent = 'Articles';
    const aboutLink = nav.querySelector('a[href="/about/"]');
    nav.insertBefore(articlesLink, aboutLink || null);
  }
  document.querySelectorAll('.footer-nav').forEach(function (footerNav) {
    if (!footerNav.querySelector('a[href="/articles/"]')) {
      const articlesLink = document.createElement('a');
      articlesLink.href = '/articles/';
      articlesLink.textContent = 'Articles';
      const aboutLink = footerNav.querySelector('a[href="/about/"]');
      footerNav.insertBefore(articlesLink, aboutLink || null);
    }
  });
  if (toggle && nav) {
    toggle.addEventListener('click', function () {
      const open = nav.classList.toggle('is-open');
      toggle.setAttribute('aria-expanded', String(open));
    });
    nav.querySelectorAll('a').forEach(function (link) {
      link.addEventListener('click', function () {
        nav.classList.remove('is-open');
        toggle.setAttribute('aria-expanded', 'false');
      });
    });
  }
  document.querySelectorAll('[data-year]').forEach(function (node) {
    node.textContent = new Date().getFullYear();
  });
}());

(function () {
  const results = document.querySelector('[data-study-results]');
  if (!results) return;

  const search = document.querySelector('[data-study-search]');
  const statusButtons = Array.from(document.querySelectorAll('[data-study-status-filter]'));
  const sortButtons = Array.from(document.querySelectorAll('[data-study-sort]'));
  const status = document.querySelector('[data-study-status]');
  const refresh = document.querySelector('[data-study-refresh]');
  const error = document.querySelector('[data-study-error]');
  const retrieved = document.querySelector('[data-study-retrieved]');
  const topicButtons = Array.from(document.querySelectorAll('[data-study-topic]'));
  const designButtons = Array.from(document.querySelectorAll('[data-study-design]'));
  let studies = [];
  let loading = false;
  let selectedTopic = '';
  let selectedDesign = 'all';
  let selectedStatus = '';
  let selectedSort = 'priority';

  const statusLabels = {
    RECRUITING: 'Recruiting',
    NOT_YET_RECRUITING: 'Not yet recruiting',
    ENROLLING_BY_INVITATION: 'Enrolling by invitation',
    ACTIVE_NOT_RECRUITING: 'Active, not recruiting',
    SUSPENDED: 'Suspended'
  };
  const statusOrder = {
    RECRUITING: 0,
    NOT_YET_RECRUITING: 1,
    ENROLLING_BY_INVITATION: 2,
    ACTIVE_NOT_RECRUITING: 3,
    SUSPENDED: 4
  };
  const topicPatterns = {
    pain: /\bpain\b|migraine|headache|analges|fibromyalgia|neuropathic/i,
    dental: /dental|dentistry|\boral\b|tooth|teeth|periodont|gingiv|temporomandibular|mucositis/i,
    wound: /wound|ulcer|\bskin\b|dermat|burn|alopecia|scar|pressure sore/i,
    neurology: /neurolog|stroke|brain|parkinson|dementia|cognitive|multiple sclerosis|epilep|spinal cord|neuropathy/i,
    musculoskeletal: /musculoskeletal|muscle|bone|joint|tendon|osteoarthritis|osteoporosis|fracture|arthritis|tendinopathy|back pain|neck pain/i,
    eye: /\beye\b|ophthalm|retina|macular|glaucoma|cornea|ocular/i,
    cardiovascular: /cardio|heart|vascular|blood pressure|hypertension|ischemi|circulation/i
  };
  const dateLabel = function (value) {
    if (!value) return 'Not reported';
    const match = /^(\d{4})(?:-(\d{2}))?(?:-(\d{2}))?$/.exec(value);
    if (!match) return value;
    if (!match[2]) return match[1];
    const month = new Date(Number(match[1]), Number(match[2]) - 1, 1);
    const options = match[3]
      ? { day: 'numeric', month: 'short', year: 'numeric' }
      : { month: 'long', year: 'numeric' };
    if (match[3]) month.setDate(Number(match[3]));
    return new Intl.DateTimeFormat('en', options).format(month);
  };
  const addText = function (parent, tag, className, value) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    node.textContent = value;
    parent.appendChild(node);
    return node;
  };

  function drawCard(study) {
    const card = document.createElement('article');
    card.className = 'trial-card';

    const main = document.createElement('div');
    main.className = 'trial-study-main';
    addText(main, 'h3', 'trial-title', study.title);
    if (study.conditions.length) {
      addText(main, 'p', 'trial-conditions', study.conditions.join(' · '));
    }
    const meta = document.createElement('p');
    meta.className = 'trial-meta';
    const metaParts = [];
    if (study.sponsor) metaParts.push('Sponsor: ' + study.sponsor);
    metaParts.push('Country: ' + (study.countries.length ? study.countries.join(', ') : 'not reported'));
    meta.textContent = metaParts.join(' · ');
    main.appendChild(meta);
    card.appendChild(main);

    const facts = document.createElement('div');
    facts.className = 'trial-facts';

    const statusFact = document.createElement('div');
    statusFact.className = 'trial-fact';
    addText(statusFact, 'span', 'trial-fact-label', 'Registry status');
    const badge = addText(statusFact, 'span', 'trial-status', statusLabels[study.status] || study.status);
    badge.dataset.status = study.status;
    facts.appendChild(statusFact);

    const enrollmentFact = document.createElement('div');
    enrollmentFact.className = 'trial-fact';
    addText(enrollmentFact, 'span', 'trial-fact-label', study.enrollmentType === 'ESTIMATED'
      ? 'Target participants'
      : study.enrollmentType === 'ACTUAL' ? 'Participants enrolled' : 'Participant count');
    addText(enrollmentFact, 'strong', 'trial-fact-value', study.enrollmentCount == null
      ? 'Not reported'
      : new Intl.NumberFormat('en').format(study.enrollmentCount));
    facts.appendChild(enrollmentFact);

    const completionFact = document.createElement('div');
    completionFact.className = 'trial-fact';
    addText(completionFact, 'span', 'trial-fact-label', study.completionType === 'ACTUAL'
      ? 'Study completed'
      : study.completionType === 'ESTIMATED' ? 'Est. completion' : 'Completion date');
    addText(completionFact, 'strong', 'trial-fact-value', dateLabel(study.completionDate));
    facts.appendChild(completionFact);
    card.appendChild(facts);

    const side = document.createElement('div');
    side.className = 'trial-card-side';
    addText(side, 'span', 'trial-updated', study.updated
      ? 'Updated ' + dateLabel(study.updated)
      : 'Update date not reported');

    const link = document.createElement('a');
    link.className = 'trial-record';
    link.href = 'https://clinicaltrials.gov/study/' + encodeURIComponent(study.id);
    link.target = '_blank';
    link.rel = 'noopener noreferrer';
    link.textContent = study.id + ' · Registry ↗';
    side.appendChild(link);
    card.appendChild(side);
    return card;
  }

  function render() {
    const needle = search.value.trim().toLocaleLowerCase();
    const chosenStatus = selectedStatus;
    const sortBy = selectedSort;
    const matches = studies.filter(function (study) {
      const statusMatches = !chosenStatus || study.status === chosenStatus;
      const topicText = [study.title, study.allConditions.join(' '), study.interventionText].join(' ');
      const matchesAnyTopic = Object.keys(topicPatterns).some(function (topic) {
        return topicPatterns[topic].test(topicText);
      });
      const topicMatches = !selectedTopic || (selectedTopic === 'other'
        ? !matchesAnyTopic
        : topicPatterns[selectedTopic].test(topicText));
      const designMatches = selectedDesign === 'all'
        || (selectedDesign === 'randomized' ? study.randomized : !study.randomized);
      const haystack = [
        study.title,
        study.id,
        study.sponsor,
        study.interventionText,
        study.allConditions.join(' '),
        study.countries.join(' ')
      ].join(' ').toLocaleLowerCase();
      return statusMatches && topicMatches && designMatches && (!needle || haystack.includes(needle));
    });
    const ordered = matches.slice().sort(function (a, b) {
      if (sortBy === 'participants-desc' || sortBy === 'participants-asc') {
        if (a.enrollmentCount == null && b.enrollmentCount != null) return 1;
        if (a.enrollmentCount != null && b.enrollmentCount == null) return -1;
        if (a.enrollmentCount != null && b.enrollmentCount != null) {
          const participantDifference = sortBy === 'participants-desc'
            ? b.enrollmentCount - a.enrollmentCount
            : a.enrollmentCount - b.enrollmentCount;
          if (participantDifference) return participantDifference;
        }
      } else if (sortBy === 'completion-asc') {
        if (!a.completionDate && b.completionDate) return 1;
        if (a.completionDate && !b.completionDate) return -1;
        const completionDifference = (a.completionDate || '').localeCompare(b.completionDate || '');
        if (completionDifference) return completionDifference;
      } else if (sortBy === 'updated') {
        const updateDifference = (b.updated || '').localeCompare(a.updated || '');
        if (updateDifference) return updateDifference;
      }
      const rank = (statusOrder[a.status] ?? 9) - (statusOrder[b.status] ?? 9);
      if (rank) return rank;
      return (b.updated || '').localeCompare(a.updated || '');
    });

    results.replaceChildren();
    if (!ordered.length) {
      addText(results, 'p', 'empty-result', studies.length
        ? 'No studies match these search and filter settings.'
        : 'No matching records were returned by the live registry search.');
    } else {
      ordered.forEach(function (study) {
        results.appendChild(drawCard(study));
      });
    }
    status.textContent = loading
      ? 'Loading current registry records…'
      : (needle || chosenStatus || selectedTopic || selectedDesign !== 'all'
        ? 'Showing ' + ordered.length + ' of ' + studies.length + ' matching studies.'
        : 'Showing all ' + studies.length + ' matching studies.');
  }

  async function loadStudies() {
    if (loading) return;
    loading = true;
    error.hidden = true;
    refresh.disabled = true;
    refresh.textContent = 'Loading…';
    status.textContent = 'Loading current registry records…';

    const params = new URLSearchParams({
      'query.term': 'photobiomodulation',
      'filter.overallStatus': 'RECRUITING,NOT_YET_RECRUITING,ENROLLING_BY_INVITATION,ACTIVE_NOT_RECRUITING,SUSPENDED',
      pageSize: '1000',
      format: 'json',
      fields: 'NCTId,BriefTitle,OverallStatus,Condition,StudyType,DesignAllocation,InterventionName,InterventionDescription,LeadSponsorName,LocationCountry,LastUpdatePostDate,CompletionDate,EnrollmentCount,EnrollmentType'
    });
    try {
      const response = await fetch('https://clinicaltrials.gov/api/v2/studies?' + params.toString(), {
        headers: { Accept: 'application/json' },
        cache: 'no-store'
      });
      if (!response.ok) throw new Error('Registry request failed');
      const payload = await response.json();
      studies = (payload.studies || []).map(function (entry) {
        const protocol = entry.protocolSection || {};
        const identification = protocol.identificationModule || {};
        const statusModule = protocol.statusModule || {};
        const sponsorModule = protocol.sponsorCollaboratorsModule || {};
        const conditionsModule = protocol.conditionsModule || {};
        const designModule = protocol.designModule || {};
        const designInfo = designModule.designInfo || {};
        const enrollmentInfo = designModule.enrollmentInfo || {};
        const completionInfo = statusModule.completionDateStruct || {};
        const interventions = (protocol.armsInterventionsModule || {}).interventions || [];
        const locations = (protocol.contactsLocationsModule || {}).locations || [];
        const conditionList = (conditionsModule.conditions || []).filter(Boolean);
        return {
          id: identification.nctId || '',
          title: identification.briefTitle || 'Untitled registered study',
          status: statusModule.overallStatus || 'UNKNOWN',
          updated: (statusModule.lastUpdatePostDateStruct || {}).date || '',
          completionDate: completionInfo.date || '',
          completionType: completionInfo.type || '',
          enrollmentCount: Number.isFinite(enrollmentInfo.count) ? enrollmentInfo.count : null,
          enrollmentType: enrollmentInfo.type || '',
          randomized: designInfo.allocation === 'RANDOMIZED',
          sponsor: (sponsorModule.leadSponsor || {}).name || '',
          conditions: conditionList.slice(0, 4),
          allConditions: conditionList,
          interventionText: interventions.map(function (intervention) {
            return [intervention.name, intervention.description].filter(Boolean).join(' ');
          }).join(' '),
          countries: Array.from(new Set(locations.map(function (location) {
            return location.country;
          }).filter(Boolean))).sort()
        };
      }).filter(function (study) {
        const registryText = study.title + ' ' + study.interventionText;
        const explicitPbmTerm = /photobiomodulation|\bPBM\b|\bLLLT\b|low[- ]level (?:laser|light)|red[- ]light therapy|near[- ]infrared light therapy/i.test(registryText);
        const photodynamicOnly = /photodynamic therapy/i.test(registryText) && !explicitPbmTerm;
        return study.id && statusLabels[study.status] && !photodynamicOnly;
      });
      const now = new Date();
      retrieved.textContent = new Intl.DateTimeFormat('en', {
        day: 'numeric', month: 'long', year: 'numeric'
      }).format(now);
      retrieved.dateTime = now.toISOString();
      loading = false;
      render();
    } catch (requestError) {
      loading = false;
      studies = [];
      results.replaceChildren();
      status.textContent = 'The live registry list is temporarily unavailable.';
      error.hidden = false;
    } finally {
      refresh.disabled = false;
      refresh.textContent = 'Refresh list';
    }
  }

  search.addEventListener('input', function () {
    render();
  });
  topicButtons.forEach(function (button) {
    button.addEventListener('click', function () {
      selectedTopic = button.dataset.studyTopic === 'all' ? '' : button.dataset.studyTopic;
      topicButtons.forEach(function (topicButton) {
        const activeTopic = selectedTopic || 'all';
        topicButton.setAttribute('aria-pressed', String(topicButton.dataset.studyTopic === activeTopic));
      });
      render();
    });
  });
  designButtons.forEach(function (button) {
    button.addEventListener('click', function () {
      selectedDesign = button.dataset.studyDesign;
      designButtons.forEach(function (designButton) {
        designButton.setAttribute('aria-pressed', String(designButton.dataset.studyDesign === selectedDesign));
      });
      render();
    });
  });

  statusButtons.forEach(function (button) {
    button.addEventListener('click', function () {
      selectedStatus = button.dataset.studyStatusFilter === 'all' ? '' : button.dataset.studyStatusFilter;
      statusButtons.forEach(function (item) {
        item.setAttribute('aria-pressed', String(item === button));
      });
      render();
    });
  });

  sortButtons.forEach(function (button) {
    button.addEventListener('click', function () {
      selectedSort = button.dataset.studySort;
      sortButtons.forEach(function (item) {
        item.setAttribute('aria-pressed', String(item === button));
      });
      render();
    });
  });
  refresh.addEventListener('click', loadStudies);
  loadStudies();
}());
