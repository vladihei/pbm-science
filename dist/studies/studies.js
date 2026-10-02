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
  var sourceDataTimestamp = document.querySelector('[data-source-data-timestamp]');
  var qualityReview = document.querySelector('[data-quality-review]');
  var reuseStatus = document.querySelector('[data-reuse-status]');
  var sourcesDetails = document.querySelector('[data-sources]');
  var sourcesList = document.querySelector('[data-source-list]');
  var records = [];

  var ongoingGroups = new Set(['ongoing']);
  var statusLabels = {
    recruiting: 'Recruiting',
    not_yet_recruiting: 'Not yet recruiting',
    enrolling_by_invitation: 'Enrolling by invitation',
    active_not_recruiting: 'Active, not recruiting',
    suspended: 'Suspended',
    completed: 'Completed',
    recruitment_completed: 'Recruitment completed',
    terminated: 'Terminated',
    withdrawn: 'Withdrawn',
    status_unknown: 'Status unknown',
    status_unclear: 'Status unclear'
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
    titleLink.href = record.source_url;
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
      ['Study start', record.start_date ? dateLabel(record.start_date) : null],
      ['Primary completion', record.primary_completion_date ? dateLabel(record.primary_completion_date) : null],
      ['Study completion', record.study_completion_date ? dateLabel(record.study_completion_date) : null],
      ['Registry last updated', record.source_updated_on ? dateLabel(record.source_updated_on) : null],
      ['Snapshot checked', record.source_retrieved_on ? dateLabel(record.source_retrieved_on) : null]
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
    sourceLink.href = record.source_url;
    sourceLink.target = '_blank';
    sourceLink.rel = 'noopener noreferrer';
    sourceLink.textContent = 'Open original registry record';
    side.appendChild(sourceLink);
    article.appendChild(side);
    return article;
  }

  function render() {
    container.replaceChildren();
    statusSelect.options[0].textContent = viewSelect.value === 'ongoing' ? 'All ongoing statuses' : 'All statuses';
    var visible = records.filter(recordMatches);
    visible.forEach(function (record) { container.appendChild(renderCard(record)); });
    count.textContent = visible.length + (visible.length === 1 ? ' registry record shown' : ' registry records shown');
    empty.hidden = visible.length > 0;
    if (records.length && visible.length === 0) {
      emptyTitle.textContent = 'No matching studies';
      emptyCopy.textContent = 'Change or clear the filters to see other records.';
    }
  }

  function showDate(node, prefix, value) {
    node.textContent = prefix + ': ' + (value ? dateLabel(value) : 'not recorded');
  }

  function showSources(sources) {
    var entries = Array.isArray(sources) ? sources : [];
    sourcesList.replaceChildren();
    if (!entries.length) {
      sourcesDetails.hidden = true;
      return;
    }
    entries.sort(function (a, b) { return a.registry.localeCompare(b.registry); }).forEach(function (source) {
      var item = document.createElement('li');
      item.textContent = source.registry + ': ' + source.search_hit_count + ' unique query hits; ' +
        source.ongoing_status_count + ' report an ongoing registry status. Snapshot checked ' +
        dateLabel(source.retrieved_on) + (source.data_timestamp ? '; source data timestamp ' + source.data_timestamp : '');
      sourcesList.appendChild(item);
    });
    sourcesDetails.hidden = false;
  }

  function showUnavailable(data) {
    records = [];
    render();
    empty.hidden = false;
    emptyTitle.textContent = data.snapshot_status === 'awaiting_source_review'
      ? 'Direct-source records are awaiting review'
      : 'Direct-registry data are being prepared';
    emptyCopy.textContent = data.snapshot_status === 'awaiting_source_review'
      ? 'The database will show records after the source reuse review and the 50-record quality check are complete.'
      : 'A direct-registry snapshot is not available yet.';
    count.textContent = 'No reviewed direct-registry records are available in this snapshot.';
  }

  fetch('/studies/ongoing-studies.json', { cache: 'no-store' })
    .then(function (response) {
      if (!response.ok) throw new Error('Could not load the local snapshot');
      return response.json();
    })
    .then(function (data) {
      showDate(retrieved, 'Snapshot collected', data.retrieved_on);
      if (sourceDataTimestamp) {
        sourceDataTimestamp.textContent = 'ClinicalTrials.gov data timestamp: ' +
          (data.source_data_timestamp || 'not recorded (records will not be published)');
      }
      if (qualityReview && data.quality_review) {
        var audit = data.quality_review;
        qualityReview.textContent = 'Source-specific audit (' + (audit.reviewed_on || 'date not recorded') + '): ' +
          (audit.checked_records || 0) + ' checked; ' + (audit.relevant_records || 0) + ' in scope; ' +
          (audit.scope_unresolved_records || 0) + ' scope unresolved; ' +
          (audit.out_of_scope_records || 0) + ' out of scope; ' +
          (audit.status_mapping_unresolved_records || 0) + ' statuses unknown';
      }
      if (reuseStatus && data.reuse_review) {
        reuseStatus.textContent = 'Source reuse review: ' + (data.reuse_review.status || 'not checked');
      }
      showSources(data.sources);
      if (data.snapshot_status !== 'ready') {
        showUnavailable(data);
        return;
      }
      records = Array.isArray(data.records) ? data.records : [];
      setOptions(registrySelect, Array.from(new Set(records.map(function (r) { return r.registry; }).filter(Boolean))).sort(), 'All registries');
      setOptions(countrySelect, Array.from(new Set(records.flatMap(function (r) { return r.countries || []; }))).sort(), 'All countries');
      var statuses = Array.from(new Set(records.map(function (r) { return r.status; }).filter(Boolean))).sort();
      setOptions(statusSelect, statuses, 'All ongoing statuses');
      Array.from(statusSelect.options).forEach(function (option) {
        if (statusLabels[option.value]) option.textContent = statusLabels[option.value];
      });
      if (!records.length) {
        empty.hidden = false;
        emptyTitle.textContent = 'No studies have passed review yet';
        emptyCopy.textContent = 'The database will display records after the direct-source review gate is met.';
      }
      render();
    })
    .catch(function () {
      showUnavailable({ snapshot_status: 'awaiting_export' });
      emptyTitle.textContent = 'No approved direct-registry snapshot is available';
      emptyCopy.textContent = 'Records will appear after the source reuse and quality checks pass.';
    });

  [search, viewSelect, registrySelect, countrySelect, statusSelect].forEach(function (control) {
    control.addEventListener('input', render);
    control.addEventListener('change', render);
  });
}());
