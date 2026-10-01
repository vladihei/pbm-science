(function () {
  var container = document.querySelector('[data-records]');
  if (!container) return;

  var search = document.querySelector('[data-search]');
  var viewSelect = document.querySelector('[data-view]');
  var registrySelect = document.querySelector('[data-registry]');
  var countrySelect = document.querySelector('[data-country]');
  var statusSelect = document.querySelector('[data-status]');
  var count = document.querySelector('[data-result-count]');
  var empty = document.querySelector('[data-empty]');
  var emptyTitle = document.querySelector('[data-empty-title]');
  var emptyCopy = document.querySelector('[data-empty-copy]');
  var retrieved = document.querySelector('[data-retrieved]');
  var processed = document.querySelector('[data-processed]');
  var qualityReview = document.querySelector('[data-quality-review]');
  var importsDetails = document.querySelector('[data-imports]');
  var importsList = document.querySelector('[data-import-list]');
  var records = [];

  var ongoingGroups = new Set(['ongoing']);
  var statusLabels = {
    recruiting: 'Recruiting',
    not_yet_recruiting: 'Not yet recruiting',
    enrolling_by_invitation: 'Enrolling by invitation',
    active_not_recruiting: 'Active, not recruiting',
    suspended: 'Suspended',
    completed: 'Completed',
    terminated: 'Terminated',
    withdrawn: 'Withdrawn'
  };

  function text(parent, tag, className, value) {
    var node = document.createElement(tag);
    if (className) node.className = className;
    node.textContent = value || 'Not reported';
    parent.appendChild(node);
    return node;
  }

  function setOptions(select, values, firstLabel) {
    var selected = select.value;
    while (select.options.length > 1) select.remove(1);
    values.forEach(function (value) {
      var option = document.createElement('option');
      option.value = value;
      option.textContent = value;
      select.appendChild(option);
    });
    select.options[0].textContent = firstLabel;
    if (values.indexOf(selected) >= 0) select.value = selected;
  }

  function dateLabel(value) {
    if (!value) return 'Not reported';
    var match = /^(\d{4})(?:-(\d{2}))?(?:-(\d{2}))?$/.exec(value);
    if (!match) return value;
    var date = new Date(Number(match[1]), Number(match[2] || '1') - 1, Number(match[3] || '1'));
    var options = match[3]
      ? { day: 'numeric', month: 'short', year: 'numeric' }
      : match[2] ? { month: 'long', year: 'numeric' } : { year: 'numeric' };
    return new Intl.DateTimeFormat('en', options).format(date);
  }

  function recordMatches(record) {
    var query = (search.value || '').trim().toLowerCase();
    var haystack = [
      record.title,
      record.primary_id,
      record.registry,
      record.sponsor,
      (record.secondary_ids || []).join(' '),
      (record.conditions || []).join(' '),
      (record.interventions || []).join(' '),
      (record.countries || []).join(' '),
      record.study_type,
      record.phase
    ].join(' ').toLowerCase();
    if (query && haystack.indexOf(query) < 0) return false;
    if (viewSelect.value === 'ongoing' && !ongoingGroups.has(record.status_group)) return false;
    if (registrySelect.value && record.registry !== registrySelect.value) return false;
    if (countrySelect.value && (record.countries || []).indexOf(countrySelect.value) < 0) return false;
    if (statusSelect.value && record.status !== statusSelect.value) return false;
    return true;
  }

  function renderCard(record) {
    var article = document.createElement('article');
    article.className = 'ictrp-record';
    var main = document.createElement('div');
    var heading = document.createElement('h2');
    var titleLink = document.createElement('a');
    titleLink.href = record.source_url || record.ictrp_url;
    titleLink.target = '_blank';
    titleLink.rel = 'noopener noreferrer';
    titleLink.textContent = record.title;
    heading.appendChild(titleLink);
    main.appendChild(heading);
    if ((record.conditions || []).length) {
      text(main, 'p', 'ictrp-condition', record.conditions.join(' · '));
    }

    var fields = document.createElement('dl');
    fields.className = 'ictrp-fields';
    [
      ['Intervention', (record.interventions || []).join(' · ')],
      ['Country', (record.countries || []).join(', ')],
      ['Study type', record.study_type],
      ['Phase', record.phase],
      ['Target sample', record.target_sample_size == null ? null : String(record.target_sample_size)],
      ['Sponsor', record.sponsor],
      ['Registration date', record.registration_date ? dateLabel(record.registration_date) : null],
      ['Last enrollment', record.last_enrollment_date ? dateLabel(record.last_enrollment_date) : null],
      ['Primary completion', record.primary_completion_date ? dateLabel(record.primary_completion_date) : null],
      ['Study completion', record.study_completion_date ? dateLabel(record.study_completion_date) : null],
      ['Estimated completion', record.estimated_completion_date ? dateLabel(record.estimated_completion_date) : null],
      ['Results completed', record.results_completed_date ? dateLabel(record.results_completed_date) : null],
      ['Record last refreshed', record.last_refreshed_on ? dateLabel(record.last_refreshed_on) : null],
      ['ICTRP record date', record.data_processed_by_ictrp_on ? dateLabel(record.data_processed_by_ictrp_on) : null]
    ].forEach(function (pair) {
      if (pair[1] == null || pair[1] === '') return;
      var item = document.createElement('div');
      text(item, 'dt', '', pair[0]);
      text(item, 'dd', '', pair[1]);
      fields.appendChild(item);
    });
    main.appendChild(fields);
    article.appendChild(main);

    var side = document.createElement('div');
    side.className = 'ictrp-record-side';
    var reportedStatus = statusLabels[record.status] || record.status_raw || 'Status not reported';
    var badge = text(side, 'span', 'ictrp-status', 'Registry reports: ' + reportedStatus);
    badge.dataset.status = record.status || '';
    var identifiers = document.createElement('div');
    identifiers.className = 'ictrp-identifiers';
    text(identifiers, 'strong', '', record.registry);
    text(identifiers, 'span', '', record.primary_id);
    if ((record.secondary_ids || []).length) text(identifiers, 'span', '', 'Also: ' + record.secondary_ids.join(', '));
    side.appendChild(identifiers);
    var sourceLink = document.createElement('a');
    sourceLink.className = 'ictrp-source-link';
    sourceLink.href = record.source_url || record.ictrp_url;
    sourceLink.target = '_blank';
    sourceLink.rel = 'noopener noreferrer';
    sourceLink.textContent = record.source_link_kind === 'original_registry'
      ? 'Open original registry record'
      : 'Open ICTRP record';
    side.appendChild(sourceLink);
    article.appendChild(side);
    return article;
  }

  function render() {
    container.replaceChildren();
    statusSelect.options[0].textContent = viewSelect.value === 'ongoing' ? 'All current statuses' : 'All statuses';
    var visible = records.filter(recordMatches);
    visible.forEach(function (record) { container.appendChild(renderCard(record)); });
    count.textContent = visible.length + (visible.length === 1 ? ' pilot record shown' : ' pilot records shown');
    empty.hidden = visible.length > 0;
    if (records.length && visible.length === 0) {
      emptyTitle.textContent = 'No matching studies';
      emptyCopy.textContent = 'Change or clear the filters to see other pilot records.';
    }
  }

  function showDate(node, prefix, value) {
    node.textContent = prefix + ': ' + (value ? dateLabel(value) : 'not stated in export');
  }

  function showImportDates(importDates) {
    var entries = Object.entries(importDates || {}).filter(function (entry) { return entry[1]; });
    importsList.replaceChildren();
    if (!entries.length) {
      importsDetails.hidden = true;
      return;
    }
    entries.sort(function (a, b) { return a[0].localeCompare(b[0]); }).forEach(function (entry) {
      var item = document.createElement('li');
      item.textContent = entry[0] + ': ' + dateLabel(entry[1]);
      importsList.appendChild(item);
    });
    importsDetails.hidden = false;
  }

  function showUnavailable(data) {
    records = [];
    render();
    empty.hidden = false;
    emptyTitle.textContent = data.snapshot_status === 'awaiting_validation'
      ? 'The ICTRP search is still being validated'
      : 'ICTRP data are being prepared';
    emptyCopy.textContent = data.snapshot_status === 'awaiting_validation'
      ? 'Search results are not shown until the sample review is complete.'
      : 'The registry export and its quality review have not been added yet.';
    count.textContent = 'No ICTRP pilot records are available in this snapshot.';
  }

  fetch('/studies/ongoing-studies.json', { cache: 'no-store' })
    .then(function (response) {
      if (!response.ok) throw new Error('Could not load the local snapshot');
      return response.json();
    })
    .then(function (data) {
      showDate(retrieved, 'PBM.science retrieval date', data.retrieved_on);
      showDate(processed, 'ICTRP processing date', data.data_processed_by_ictrp_on);
      if (qualityReview && data.quality_review) {
        var audit = data.quality_review;
        qualityReview.textContent = 'Initial sample audit: ' + (audit.checked_records || 0) + ' checked; ' +
          (audit.relevant_records || 0) + ' in scope; ' + (audit.unresolved_records || 0) +
          ' unresolved; ' + (audit.out_of_scope_records || 0) + ' out of scope';
      }
      showImportDates(data.registry_import_dates);
      if (data.snapshot_status !== 'ready') {
        showUnavailable(data);
        return;
      }
      records = Array.isArray(data.records) ? data.records : [];
      setOptions(registrySelect, Array.from(new Set(records.map(function (r) { return r.registry; }).filter(Boolean))).sort(), 'All registries');
      setOptions(countrySelect, Array.from(new Set(records.flatMap(function (r) { return r.countries || []; }))).sort(), 'All countries');
      var statuses = Array.from(new Set(records.map(function (r) { return r.status; }).filter(Boolean))).sort();
      setOptions(statusSelect, statuses, 'All current statuses');
      Array.from(statusSelect.options).forEach(function (option) {
        if (statusLabels[option.value]) option.textContent = statusLabels[option.value];
      });
      if (!records.length) {
        empty.hidden = false;
        emptyTitle.textContent = 'No studies have passed review yet';
        emptyCopy.textContent = 'The pilot database will display records after the review gate has been met.';
      }
      render();
    })
    .catch(function () {
      showUnavailable({ snapshot_status: 'awaiting_export' });
      emptyTitle.textContent = 'The local ICTRP snapshot could not be loaded';
      emptyCopy.textContent = 'The registry pilot is temporarily unavailable while the snapshot is repaired.';
    });

  [search, viewSelect, registrySelect, countrySelect, statusSelect].forEach(function (control) {
    control.addEventListener('input', render);
    control.addEventListener('change', render);
  });
}());
