/**
 * reset_lineup.jsx — Reseteaza proiectul AE la starea de template
 * ════════════════════════════════════════════════════════════════
 * Ce face:
 *   1. Protejeaza template-ul home_player_01 (nu il sterge)
 *   2. Sterge layerele home/away player/sub din MAIN COMP
 *   3. Sterge comp-urile generate (Stats_*, PT_*, home_player_02+, etc.)
 *   4. Reseteaza textele: Home Team, Away Team, Score
 *   5. Reseteaza slidere rating la 0
 *   6. Redenumeste comp-ul echipelor inapoi la "Home - Away"
 *   7. Sterge fisierele imagine generate (home_player_*.png etc.)
 *   8. Redenumeste template-ul inapoi la "home_player_01"
 * ════════════════════════════════════════════════════════════════
 */

// ── Configurare (trebuie sa coincida cu populate_lineup.jsx) ───
var MAIN_COMP_NAME           = "MAIN COMP";
var LAYER_HOME_TEAM          = "Home Team";
var LAYER_AWAY_TEAM          = "Away Team";
var LAYER_SCORE              = "Score";
var HOME_RATING_COMP         = "Home Rating";
var AWAY_RATING_COMP         = "Away Rating";
var HOME_RATING_LAYER        = "Home - Rating";
var AWAY_RATING_LAYER        = "Away - Rating";
var MATCH_NAME_COMP_ORIGINAL = "Home - Away";
var TEMPLATE_COMP_NAME       = "home_player_01";


(function () {

    // ── Gaseste Main Comp ─────────────────────────────────────
    var mainComp = findCompByName(MAIN_COMP_NAME);
    if (!mainComp) mainComp = app.project.activeItem;
    if (!mainComp || !(mainComp instanceof CompItem)) {
        alert("Please select MAIN COMP and try again.");
        return;
    }

    // ── Citeste data.json ─────────────────────────────────────
    var scriptFile = new File($.fileName);
    var dir        = scriptFile.parent.fsName;

    // Daca scriptul e apelat din panel, folderul poate veni ca variabila globala
    if (typeof $.global.__LINEUP_SCRIPTS_DIR__ !== "undefined" && $.global.__LINEUP_SCRIPTS_DIR__) {
        dir = $.global.__LINEUP_SCRIPTS_DIR__;
    }

    var currentHomeName = "";
    var currentAwayName = "";
    var jf = new File(normPath(dir) + "/flashscore_output/data.json");
    if (jf.exists) {
        try {
            jf.open("r");
            var data = JSON.parse(jf.read());
            jf.close();
            currentHomeName = data.match.home_team || "";
            currentAwayName = data.match.away_team || "";
        } catch(e) {}
    }

    // ── Citeste template_state.json (daca exista) ─────────────
    var DEFAULT_HOME_TEXT  = "Home Team";
    var DEFAULT_AWAY_TEXT  = "Away Team";
    var DEFAULT_SCORE_TEXT = "0 - 0";
    var DEFAULT_HOME_RATING = 0;
    var DEFAULT_AWAY_RATING = 0;
    var DEFAULT_MATCH_COMP_NAME = MATCH_NAME_COMP_ORIGINAL;

    var stateFile = new File(normPath(dir) + "/flashscore_output/template_state.json");
    if (stateFile.exists) {
        try {
            stateFile.open("r");
            var stateData = JSON.parse(stateFile.read());
            stateFile.close();
            if (stateData.homeTeamText  !== undefined) DEFAULT_HOME_TEXT      = stateData.homeTeamText;
            if (stateData.awayTeamText  !== undefined) DEFAULT_AWAY_TEXT      = stateData.awayTeamText;
            if (stateData.scoreText     !== undefined) DEFAULT_SCORE_TEXT     = stateData.scoreText;
            if (stateData.homeRating    !== undefined) DEFAULT_HOME_RATING    = stateData.homeRating;
            if (stateData.awayRating    !== undefined) DEFAULT_AWAY_RATING    = stateData.awayRating;
            if (stateData.matchCompName !== undefined) DEFAULT_MATCH_COMP_NAME = stateData.matchCompName;
        } catch(e) {}
    }

    app.beginUndoGroup("Reset Lineup Template");

    // ════════════════════════════════════════════════════════
    //  PASUL 1: Protejeaza template-ul home_player_01
    //  Cauta instanta care NU este folosita ca layer in MAIN COMP
    // ════════════════════════════════════════════════════════
    var templateComp = findTemplateComp(TEMPLATE_COMP_NAME, mainComp);
    var BACKUP_NAME  = "__TEMPLATE_BACKUP__";
    if (templateComp) {
        templateComp.name = BACKUP_NAME;
    } else {
        // Poate __TEMPLATE_BACKUP__ exista deja (rulare intrerupta anterior)
        templateComp = findCompByName(BACKUP_NAME);
    }

    // ════════════════════════════════════════════════════════
    //  PASUL 2: Sterge layerele generate din MAIN COMP
    // ════════════════════════════════════════════════════════
    var del = [];
    for (var i = 1; i <= mainComp.numLayers; i++) {
        var nm = mainComp.layer(i).name;
        if (/^(home|away)_(player|sub)_\d+$/.test(nm))
            del.push(mainComp.layer(i));
    }
    for (var j = 0; j < del.length; j++) del[j].remove();
    var removedLayers = del.length;

    // ════════════════════════════════════════════════════════
    //  PASUL 2b: Sterge markere din MAIN COMP
    // ════════════════════════════════════════════════════════
    try {
        var markerProp = mainComp.markerProperty;
        for (var mi = markerProp.numKeys; mi >= 1; mi--) {
            markerProp.removeKey(mi);
        }
    } catch(e) {}

    // ════════════════════════════════════════════════════════
    //  PASUL 3: Sterge comp-urile generate din panoul de proiect
    //  (exclude BACKUP_NAME si home_player_01)
    // ════════════════════════════════════════════════════════
    var toDelete = [];
    for (var k = 1; k <= app.project.numItems; k++) {
        var it = app.project.item(k);
        if (!(it instanceof CompItem)) continue;
        if (it.name === BACKUP_NAME) continue;  // pastreaza NUMAI backup-ul, nimic altceva
        if (/^(home|away)_(player|sub)_\d+$/.test(it.name) ||
            /^Stats_(home|away)_(player|sub)_\d+$/.test(it.name) ||
            /^PT_(home|away)_(player|sub)_\d+$/.test(it.name)) {
            toDelete.push(it);
        }
    }
    for (var d = toDelete.length - 1; d >= 0; d--) {
        try { toDelete[d].remove(); } catch(e) {}
    }
    var deletedComps = toDelete.length;

    // ════════════════════════════════════════════════════════
    //  PASUL 4: Reseteaza texte in MAIN COMP
    // ════════════════════════════════════════════════════════
    setTxt(mainComp, LAYER_HOME_TEAM, DEFAULT_HOME_TEXT);
    setTxt(mainComp, LAYER_AWAY_TEAM, DEFAULT_AWAY_TEXT);
    setTxt(mainComp, LAYER_SCORE,     DEFAULT_SCORE_TEXT);

    // ════════════════════════════════════════════════════════
    //  PASUL 5: Reseteaza slidere rating la 0
    // ════════════════════════════════════════════════════════
    resetRatingSlider(HOME_RATING_COMP, HOME_RATING_LAYER, DEFAULT_HOME_RATING);
    resetRatingSlider(AWAY_RATING_COMP, AWAY_RATING_LAYER, DEFAULT_AWAY_RATING);
    resetRatingSlider(AWAY_RATING_COMP, HOME_RATING_LAYER, DEFAULT_AWAY_RATING); // fallback same name

    // ════════════════════════════════════════════════════════
    //  PASUL 6: Redenumeste comp-ul echipelor inapoi la "Home - Away"
    //           + sterge markere din el
    // ════════════════════════════════════════════════════════
    var matchComp = null;
    if (currentHomeName && currentAwayName)
        matchComp = findCompByName(currentHomeName + " - " + currentAwayName);
    if (!matchComp) {
        for (var m = 1; m <= app.project.numItems; m++) {
            var mi2 = app.project.item(m);
            if (mi2 instanceof CompItem &&
                mi2.name.indexOf(" - ") > 0 &&
                mi2.name !== MATCH_NAME_COMP_ORIGINAL &&
                mi2.name !== BACKUP_NAME &&
                !/^(home|away|Stats_|PT_)/.test(mi2.name)) {
                matchComp = mi2; break;
            }
        }
    }
    // Sterge markere INAINTE de redenumire (referinta ramane valida indiferent de nume)
    function clearCompMarkers(comp) {
        if (!comp) return;
        try {
            var _mp = comp.markerProperty;
            while (_mp.numKeys > 0) _mp.removeKey(1);
        } catch(e) {}
    }
    clearCompMarkers(matchComp);
    if (matchComp) matchComp.name = DEFAULT_MATCH_COMP_NAME;

    // Fallback: daca matchComp era null, comp-ul e deja numit "Home - Away" cu markere vechi
    clearCompMarkers(findCompByName(DEFAULT_MATCH_COMP_NAME));

    // ════════════════════════════════════════════════════════
    //  PASUL 7a: Sterge footage items importate din panoul de proiect
    //  EXCEPTIE: pastreaza footage-urile folosite de template (__TEMPLATE_BACKUP__)
    // ════════════════════════════════════════════════════════

    // Colecteaza toate footage ID-urile folosite de template (recursiv)
    var templateFootageIds = {};
    if (templateComp) collectFootageIds(templateComp, templateFootageIds);

    var toDeleteFootage = [];
    for (var fi = 1; fi <= app.project.numItems; fi++) {
        var fit = app.project.item(fi);
        try {
            if (fit.file) {
                if (templateFootageIds[fit.id]) continue; // nu sterge ce foloseste template-ul
                var fpath = (fit.file.fsName || fit.file.absoluteURI || '').toLowerCase();
                var fname = (fit.file.name || '').toLowerCase();
                if (fname === 'home_logo.png' || fname === 'away_logo.png') continue;
                if ((fpath.indexOf('flashscore_output') >= 0 &&
                     fpath.indexOf('images') >= 0) ||
                    /^(home|away)_(player|sub)_\d+\.(png|jpg|jpeg|svg)$/i.test(fname)) {
                    toDeleteFootage.push(fit);
                }
            }
        } catch(e) {}
    }
    for (var fd = toDeleteFootage.length - 1; fd >= 0; fd--) {
        try { toDeleteFootage[fd].remove(); } catch(e) {}
    }
    var deletedFootage = toDeleteFootage.length;

    // ════════════════════════════════════════════════════════
    //  PASUL 7b: Sterge TOATE fisierele din flashscore_output/images/
    // ════════════════════════════════════════════════════════
    var deletedFiles = deletePlayerImages(dir);

    // ════════════════════════════════════════════════════════
    //  PASUL 8: Redenumeste template-ul inapoi la "home_player_01"
    // ════════════════════════════════════════════════════════
    if (templateComp) {
        templateComp.name = TEMPLATE_COMP_NAME;
    } else {
        alert("WARNING: Template '" + TEMPLATE_COMP_NAME + "' was lost!\n" +
              "Reopen the AEP file from backup or recreate it.");
    }

    app.endUndoGroup();

    // ── Raport ───────────────────────────────────────────────
    var msg = "\u2713 Reset complete!\n\n";
    msg += "\u2022 " + removedLayers  + " layers removed from MAIN COMP\n";
    msg += "\u2022 " + deletedComps   + " generated comps deleted\n";
    msg += "\u2022 " + deletedFootage + " footage items removed from project\n";
    msg += "\u2022 " + deletedFiles   + " image files deleted from disk\n";
    msg += "\u2022 Texts reset";
    msg += stateFile.exists ? " (from template_state.json)" : " (default values)";
    msg += "\n";
    msg += "\u2022 Rating = " + DEFAULT_HOME_RATING + " / " + DEFAULT_AWAY_RATING + "\n";
    msg += matchComp ? ("\u2022 Comp renamed \u2192 " + DEFAULT_MATCH_COMP_NAME + "\n") : "";
    msg += templateComp ? ("\u2022 Template '" + TEMPLATE_COMP_NAME + "': OK\n") : "";
    msg += "\nProject is ready for a new run.";
    alert(msg);

})();


// ════════════════════════════════════════════════════════════
//  HELPERS
// ════════════════════════════════════════════════════════════

// Gaseste instanta template-ului care NU e folosita ca layer in mainComp
function findTemplateComp(name, mainComp) {
    var usedIds = {};
    for (var i = 1; i <= mainComp.numLayers; i++) {
        var lyr = mainComp.layer(i);
        if (lyr.source instanceof CompItem) usedIds[lyr.source.id] = true;
    }
    for (var k = 1; k <= app.project.numItems; k++) {
        var it = app.project.item(k);
        if (it instanceof CompItem && it.name === name && !usedIds[it.id])
            return it;
    }
    return null;
}

// Colecteaza recursiv ID-urile tuturor footage-urilor folosite intr-un comp
function collectFootageIds(comp, ids) {
    for (var i = 1; i <= comp.numLayers; i++) {
        var lyr = comp.layer(i);
        try {
            if (lyr.source instanceof CompItem)    collectFootageIds(lyr.source, ids);
            else if (lyr.source)                   ids[lyr.source.id] = true;
        } catch(e) {}
    }
}

function deletePlayerImages(scriptsDir) {
    // Sterge TOATE fisierele din flashscore_output/images/ (echivalent cu \images\* -Force)
    var imgDir = new Folder(normPath(scriptsDir) + "/flashscore_output/images");
    if (!imgDir.exists) return 0;
    var count = 0;
    var allFiles = imgDir.getFiles("*");
    for (var f = 0; f < allFiles.length; f++) {
        if (!(allFiles[f] instanceof File)) continue;
        var fn = allFiles[f].name.toLowerCase();
        if (fn === 'home_logo.png' || fn === 'away_logo.png') continue;  // pastreaza logo-urile
        try { allFiles[f].remove(); count++; } catch(e) {}
    }
    return count;
}

function normPath(p) {
    return (p || "").replace(/\\/g, "/").replace(/\/$/, "");
}

function findCompByName(n) {
    for (var i = 1; i <= app.project.numItems; i++) {
        var it = app.project.item(i);
        if (it instanceof CompItem && it.name === n) return it;
    }
    return null;
}
function findLayerIn(comp, n) {
    for (var i = 1; i <= comp.numLayers; i++)
        if (comp.layer(i).name === n) return comp.layer(i);
    return null;
}
function setTxt(comp, layerName, val) {
    var l = findLayerIn(comp, layerName);
    if (!l) return;
    try {
        var prop = l.property("Source Text");
        if (prop.expressionEnabled) prop.expressionEnabled = false;
        // Nu crea keyframe-uri: daca layerul e animat, sarim peste
        if (prop.numKeys && prop.numKeys > 0) return;
        var td = prop.value;
        td.text = String(val);
        try { prop.setValue(td); } catch(e1) {}
    } catch(e) {}
}
function resetRatingSlider(compName, layerName, val) {
    if (val === undefined || val === null) val = 0;
    var comp = findCompByName(compName);
    if (!comp) return;
    var lyr = findLayerIn(comp, layerName);
    if (!lyr) return;
    try { lyr.effect("Slider Control").property("Slider").setValue(val); return; } catch(e) {}
    try { lyr.effect("Slider Control").property(1).setValue(val); return; } catch(e) {}
    try { lyr.effect(1).property(1).setValue(val); } catch(e) {}
}
