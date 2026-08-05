// Chrome Proxy helper - popup
// Each row is a profile; click it to expand the proxy types that profile has
// configured, then click a type to make that profile active and apply it.

document.documentElement.lang = chrome.i18n.getUILanguage();

var CHEVRON_SVG = '<svg viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M3 4.5l3 3 3-3"/></svg>';

// Modes that are always offered but tucked behind the "More" row unless the
// profile is currently using one of them.
var SECONDARY_MODES = ['system', 'auto_detect'];

function buildModeRow(p, mode, current) {
    var $li = $('<li>').attr('data-apply', resolveMode(p, mode));
    if (mode === current) $li.addClass('current');
    $li.append($('<div>').addClass('menu')
        .append($('<div>').addClass('icon').html(modeIcon(mode)))
        .append($('<span>').addClass('text').text(modeLabel(mode))));
    return $li;
}

function buildModeList(p) {
    var $ul = $('<ul>').addClass('modes');
    var current = normalizeMode(p.mode);

    var primary = configuredModes(p).concat('direct');
    if (SECONDARY_MODES.indexOf(current) !== -1) primary.push(current);
    var extra = SECONDARY_MODES.filter(function(m) { return primary.indexOf(m) === -1; });

    primary.forEach(function(mode) { $ul.append(buildModeRow(p, mode, current)); });

    if (extra.length) {
        $ul.append($('<li>').addClass('modes-more')
            .append($('<div>').addClass('menu')
                .append($('<div>').addClass('icon').html(CHEVRON_SVG))
                .append($('<span>').addClass('text').text(i18nMessage('more_modes', 'More')))
                .append($('<span>').addClass('more-hint').text('(' + extra.map(modeLabel).join(' · ') + ')'))));
        extra.forEach(function(mode) {
            $ul.append(buildModeRow(p, mode, current).addClass('modes-extra'));
        });
    }
    return $ul;
}

function renderProfileList(profiles, activeId) {
    var $list = $('#profile-list').empty();
    Object.keys(profiles).forEach(function(id) {
        var p = profiles[id];
        var $item = $('<li>').addClass('profile-item').attr('data-profile-id', id);
        if (id === activeId) $item.addClass('active expanded');

        var $head = $('<div>').addClass('menu profile-head');
        $head.append($('<div>').addClass('icon').html(modeIcon(p.mode)));
        $head.append($('<div>').addClass('profile-name').text(p.name));
        $head.append($('<span>').addClass('chevron').html(CHEVRON_SVG));

        $item.append($head).append(buildModeList(p));
        $list.append($item);
    });
}

function refresh() {
    listProfiles(function(profiles, active) {
        renderProfileList(profiles, active);
    });
}

function configProxy() {
    if (chrome.runtime.openOptionsPage) {
        chrome.runtime.openOptionsPage();
    } else {
        window.open(chrome.runtime.getURL('options.html'));
    }
}

document.addEventListener('DOMContentLoaded', function() {
    document.querySelector('#config-proxy').addEventListener('click', configProxy);

    $('#profile-list').on('click', '.profile-head', function() {
        var $item = $(this).closest('.profile-item');
        var willExpand = !$item.hasClass('expanded');
        $('#profile-list .profile-item').removeClass('expanded');
        if (willExpand) $item.addClass('expanded');
    });

    $('#profile-list').on('click', '.modes-more', function() {
        $(this).closest('.modes').toggleClass('show-extra');
    });

    $('#profile-list').on('click', '.modes li[data-apply]', function() {
        var id = $(this).closest('.profile-item').attr('data-profile-id');
        var mode = $(this).attr('data-apply');
        if (!id || !mode) return;
        setActiveAndApplyMode(id, mode, refresh);
    });

    $('[data-i18n-content]').each(function() {
        var message = chrome.i18n.getMessage(this.getAttribute('data-i18n-content'));
        if (message) $(this).html(message);
    });

    ensureMigrated(refresh);
});

$(document).ready(function() {
    document.querySelector('.version').textContent = chrome.runtime.getManifest().version;
});
