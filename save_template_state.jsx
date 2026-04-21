/**
 * save_template_state.jsx — Salveaza starea curenta a proiectului ca stare default pentru reset
 * ════════════════════════════════════════════════════════════════════════════════════════════
 * Ce face:
 *   1. Citeste textele curente din MAIN COMP (Home Team, Away Team, Score)
 *   2. Citeste valorile sliderelor de rating (Home Rating, Away Rating)
 *   3. Citeste numele comp-ului "Home - Away" (daca a fost redenumit)
 *   4. Salveaza totul in flashscore_output/template_state.json
 *
 * Ruleaza INAINTE de a popula vreo echipa — cand proiectul este in starea de template curata.
 * ════════════════════════════════════════════════════════════════════════════════════════════
 */

var MAIN_COMP_NAME    = "MAIN COMP";
var LAYER_HOME_TEAM   = "Home Team";
var LAYER_AWAY_TEAM   = "Away Team";
var LAYER_SCORE       = "Score";
var HOME_RATING_COMP  = "Home Rating";
var AWAY_RATING_COMP  = "Away Rating";
var HOME_RATING_LAYER = "Home - Rating";
var AWAY_RATING_LAYER = "Away - Rating";
var MATCH_NAME_COMP_DEFAULT = "Home - Away";
var TEMPLATE_COMP_NAME = "home_player_01";

(function () {

    // ── Gaseste Main Comp ────────────────────────────────────────
    var mainComp = findCompByName(MAIN_COMP_NAME);
    if (!mainComp) mainComp = app.project.activeItem;
    if (!mainComp || !(mainComp instanceof CompItem)) {
        alert("Selecteaza MAIN COMP si incearca din nou.");
        return;
    }

    // ── Detecteaza folderul scripturilor ────────────────────────
    var dir = "";
    try { dir = new File($.fileName).parent.fsName; } catch(e) {}
    if (typeof $.global.__LINEUP_SCRIPTS_DIR__ !== "undefined" && $.global.__LINEUP_SCRIPTS_DIR__)
        dir = $.global.__LINEUP_SCRIPTS_DIR__;
    if (!dir) { alert("Nu pot determina folderul scripturilor."); return; }

    // ── Citeste textele din MAIN COMP ───────────────────────────
    var homeTeamText = getTxt(mainComp, LAYER_HOME_TEAM);
    var awayTeamText = getTxt(mainComp, LAYER_AWAY_TEAM);
    var scoreText    = getTxt(mainComp, LAYER_SCORE);

    // ── Citeste sliderele rating ─────────────────────────────────
    var homeRating = getSlider(HOME_RATING_COMP, HOME_RATING_LAYER);
    var awayRating = getSlider(AWAY_RATING_COMP, AWAY_RATING_LAYER);
    // fallback: daca Away Rating comp foloseste acelasi layer name ca Home
    if (awayRating === null)
        awayRating = getSlider(AWAY_RATING_COMP, HOME_RATING_LAYER);

    // ── Gaseste numele comp-ului match (Home - Away) ─────────────
    var matchCompName = MATCH_NAME_COMP_DEFAULT;
    var matchComp = findCompByName(MATCH_NAME_COMP_DEFAULT);
    if (matchComp) {
        matchCompName = matchComp.name;
    } else {
        // Cauta orice comp cu " - " care nu e generat
        for (var i = 1; i <= app.project.numItems; i++) {
            var it = app.project.item(i);
            if (it instanceof CompItem &&
                it.name.indexOf(" - ") > 0 &&
                !/^(home|away|Stats_|PT_)/.test(it.name)) {
                matchCompName = it.name;
                break;
            }
        }
    }

    // ── Construieste obiectul de stare ───────────────────────────
    var state = {
        homeTeamText : homeTeamText !== null ? homeTeamText : "Home Team",
        awayTeamText : awayTeamText !== null ? awayTeamText : "Away Team",
        scoreText    : scoreText    !== null ? scoreText    : "0 - 0",
        homeRating   : homeRating   !== null ? homeRating   : 0,
        awayRating   : awayRating   !== null ? awayRating   : 0,
        matchCompName: matchCompName,
        savedAt      : (new Date()).toString()
    };

    // ── Creeaza folderul flashscore_output daca nu exista ────────
    var outDir = new Folder(normPath(dir) + "/flashscore_output");
    if (!outDir.exists) outDir.create();

    // ── Scrie JSON ───────────────────────────────────────────────
    var stateFile = new File(normPath(dir) + "/flashscore_output/template_state.json");
    stateFile.encoding = "UTF-8";
    stateFile.open("w");
    stateFile.write(JSON.stringify(state, null, 2));
    stateFile.close();

    // ── Confirmare ───────────────────────────────────────────────
    var msg = "\u2713 Starea template-ului a fost salvata!\n\n";
    msg += "\u2022 Home Team: \""  + state.homeTeamText + "\"\n";
    msg += "\u2022 Away Team: \""  + state.awayTeamText + "\"\n";
    msg += "\u2022 Score: \""      + state.scoreText    + "\"\n";
    msg += "\u2022 Home Rating: "  + state.homeRating   + "\n";
    msg += "\u2022 Away Rating: "  + state.awayRating   + "\n";
    msg += "\u2022 Match Comp: \"" + state.matchCompName + "\"\n";
    msg += "\nReset va restaura exact aceste valori.";
    alert(msg);

})();


// ════════════════════════════════════════════════════════════
//  HELPERS
// ════════════════════════════════════════════════════════════

function getTxt(comp, layerName) {
    var lyr = findLayerIn(comp, layerName);
    if (!lyr) return null;
    try {
        var prop = lyr.property("Source Text");
        return prop.value.text;
    } catch(e) { return null; }
}

function getSlider(compName, layerName) {
    var comp = findCompByName(compName);
    if (!comp) return null;
    var lyr = findLayerIn(comp, layerName);
    if (!lyr) return null;
    try { return lyr.effect("Slider Control").property("Slider").value; } catch(e) {}
    try { return lyr.effect("Slider Control").property(1).value; } catch(e) {}
    try { return lyr.effect(1).property(1).value; } catch(e) {}
    return null;
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

function normPath(p) {
    return (p || "").replace(/\\/g, "/").replace(/\/$/, "");
}
