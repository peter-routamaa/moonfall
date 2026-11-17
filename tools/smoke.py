"""Smoke test: plays every screen and state of the game headless, on every moon, and fails on any error.

    python3 tools/smoke.py [game.html] [moon ...]        (defaults: src/moonfall.html, every moon)

Version 216 (code review: "no tests of game logic"). The other tools each look at one thing (budgets, canvases made in
a fight, pixels); this one only asks "does anything throw?", everywhere a player can go, in about half a minute:
the start screen, the intro film, the main menu and every card on it, a run (intro, falling with hazards, pause and
resume, a cafe landing, the shop, the jump back out, a death, game over, the high score table), a long fall through
the deeper layers, the self-test started and quit, the escape preview (its pop-up, then ending, quit, death), the launch and the ending, and back to the menu.
Then every answer on every card (the components card at a cafe, the cafe's launch, the ship repaired, the drone offered
at Jump in and after the ending: PRESSES below), each checked for where it leaves the game; a fall with the helper drone,
which must catch something; and a real cave claim through the high scores, the launch and the end screen, where the
mission must be counted once and the drone named.
It runs the real game in Chrome with the same seeded random numbers and stepped frames as tools/same_pixels.py, and
counts every uncaught error and rejected promise (the frame loop throws its errors on, see frame()). It also fails
if a step doesn't reach the state it should, if a card button in PRESSES was never pressed, if fewer component cards came up than cafe landings had components to show (or there was never one), which means the script or the game's flow broke, not that all is well,
and on every problem the game's own load-time checks found in its tables (window.__mfProblems, filled by
checkHazards and checkLeviathans: a hazard or Leviathan entry missing a field, or naming an attack that doesn't exist).
Exits 1 listing what failed, 2 if Chrome is missing. The website build runs it (tools/build_site.py).
"""
import os, re, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import chrome, same_pixels, test_pages

ROOT = chrome.ROOT

HOOK = ("window.__smoke = { setCard, openMenu, pause, resume, toTitle, leaveCafe, openShop, showEnd, perfStart, cafeCard, startPreview, askPreview, "
        "startRun, fillParts, get confirmKind() { return confirmKind; }, get hsFrom() { return hsFrom; }, "
        "get previewOn() { return previewSave !== null; }, get perfOn() { return perfOn; }, get cardSide() { return cardSide; }, get wakeWant() { return typeof wakeWant === 'undefined' ? false : wakeWant; } };")

# Every answer on every card that a step must press (as 'card kind: button label', see press() in the driver). The smoke
# test fails on any that was never pressed, so a step that stops short, or a card that never came up, can't pass unseen.
# A button renamed in the game is renamed here too.
PRESSES = [
    'comps: Great!', 'comps: Not yet', 'comps: Fly home!',   # the components card at a cafe (askComps)
    'launch: Not yet', 'launch: Fly home!',                  # the cafe's own launch (askLaunch, #cafeLaunchBtn)
    'repaired: Later', 'repaired: Fly home!',                # the dive that finished the ship (askRepaired)
    'drone: Not now', 'drone: Yes, bring it',                # the drone offered at Jump in (askDrone)
    'droneEnd: Great!',                                      # the drone after the standard ending (tellDroneEnd)
]

DRIVER = r"""<script>
(async () => {
  const M = window.__mf, S = window.__smoke, P = M.player, $ = id => document.getElementById(id);
  const out = { errors: [], steps: [], moon: new URLSearchParams(location.search).get('moon') || 'dust' };
  addEventListener('error', e => out.errors.push(String(e.message || e.error)));
  addEventListener('unhandledrejection', e => out.errors.push('promise: ' + String(e.reason && e.reason.message || e.reason)));
  document.addEventListener('visibilitychange', e => e.stopImmediatePropagation(), true);
  const wait = ms => new Promise(f => setTimeout(f, ms));
  const seen = new Set();   // every state the run passed through, frame by frame
  let t = performance.now() + 1000;
  // A component's card (a Leviathan escaped) gets Continue, as a player would. A step that answers the card itself turns
  // autoCard off. compCards counts the component cards that came up, compCardsWant the cafe landings with components
  // waiting to be shown (save.compsNew); tools/smoke.py fails if fewer came up, or if there was never one to show.
  let autoCard = true, cardWas = false;
  out.compCards = 0; out.compCardsWant = 0;
  const run = (n, keep) => {
    for (let i = 0; i < n; i++) {
      t += 1000 / 60; if (keep) keep(); if (autoCard) __tools.continueCard();
      const was = M.state;
      try { M.frame(t); } catch (e) { out.errors.push('frame: ' + (e && e.message || e)); }
      seen.add(M.state);
      if (was === 'landing' && M.state === 'cafe' && (M.save.compsNew || []).length) out.compCardsWant++;
      const up = __tools.cardUp(); if (up && !cardWas) out.compCards++; cardWas = up;
    }
  };
  const safe = () => { P.inv = 1; P.hp = P.max; };
  // A step does something, plays some frames, and says which state it should end in ('' for any).
  const step = async (name, want, fn, frames, keep) => {
    await wait(20);   // lets the last step's history.back() land, as a person's pace would (see phones in the game)
    try { await fn(); } catch (e) { out.errors.push(name + ': ' + (e && e.message || e)); }
    run(frames || 0, keep);
    if (__tools.cardUp()) run(1, keep);   // a component's card on the step's last frame
    const ok = !want || want.split('|').includes(M.state);
    out.steps.push({ name, state: M.state, ok });
  };
  if (document.fonts) await document.fonts.ready; await wait(200);
  out.problems = (window.__mfProblems || []).slice();   // what the game's own load-time checks found (checkHazards, checkLeviathans)
  await step('splash', 'splash', () => {}, 30);
  await step('choose moon', 'splash', () => { $('chooseBtn').click(); document.querySelector('.splash-moon[data-moon="' + out.moon + '"]').click(); }, 20);
  await step('intro film', 'opening', () => $('splashBtn').click(), 60 * 6);
  await step('skip film', 'title', () => $('introSkip').click(), 30);
  // Five taps on the pilot ask about the escape preview before START too; Not now leaves the menu as it was.
  await step('escape preview asks before START', 'title', () => S.askPreview(), 10);
  if (!$('confirmDlg').open) out.errors.push('escape preview: no pop-up before START');
  if (!$('confirmYes').disabled) out.errors.push('escape preview: its buttons answer straight away');
  await step('escape preview not now', 'title', async () => { await wait(900); $('confirmNo').click(); }, 10);
  await step('menu', 'title', () => S.openMenu(), 30);
  for (const card of ['settings', 'how', 'news', 'levi', 'badges', 'unlocks', 'moons', 'kid'])
    await step('card ' + card, 'title', () => S.setCard(card, true), 20);
  await step('cards closed', 'title', () => S.setCard(null, true), 10);
  // Jump in shows the card with the components and the moons; Back stays on the menu, Dive! starts the dive.
  await step('jump in card', 'title', () => $('startBtn').click(), 10);
  if (!$('confirmDlg').open || $('confirmMoons').hidden) out.errors.push('jump in: no card with the moons');
  await step('jump in back', 'title', () => $('confirmNo').click(), 10);
  if ($('confirmDlg').open) out.errors.push('jump in: Back left the card open');
  await step('start', 'intro|play', () => { $('startBtn').click(); $('confirmYes').click(); }, 60 * 4);
  await step('falling', 'play', () => {}, 60 * 20, safe);
  await step('pause', 'paused', () => S.pause(), 10);
  await step('resume', 'play', () => S.resume(), 10, safe);
  if (!S.wakeWant) out.errors.push('screen awake: not asked for during a run');
  // The phone's back gesture mid-run pauses instead of leaving (see phones in the game).
  await step('back gesture', 'paused', () => dispatchEvent(new PopStateEvent('popstate', { state: null })), 10);
  await step('resume after back', 'play', () => S.resume(), 10, safe);
  // The cafe with a component's card up when the phone is locked: the card is answered on the pause screen, and the
  // cafe's menu must still open on Resume.
  autoCard = false;
  await step('cafe landing', 'cafe', () => { M.save.compsNew = [M.COMPONENTS[0].id]; P.y = M.cafeInfo(1).Dl - 400; }, 60 * 12, () => { safe(); P.x = M.cafeInfo(1).padX; P.aim = P.x; });
  if (!$('confirmDlg').open) out.errors.push('cafe: no component card');
  await step('pause with the card up', 'paused', () => S.pause(), 10);
  await step('card answered while paused', 'paused', () => $('confirmYes').click(), 10);
  await step('resume to the cafe', 'cafe', () => S.resume(), 20);
  if ($('shop').hidden) out.errors.push('cafe: no menu after its card was answered while paused');
  autoCard = true;
  await step('shop', 'cafe', () => S.openShop(), 20);
  for (const face of ['shop', 'tips', 'repair']) await step('cafe card ' + face, 'cafe', () => S.cafeCard(face, true), 20);
  await step('cafe card closed', 'cafe', () => S.cafeCard(null, true), 10);
  await step('leave cafe', 'cafeJump|play', () => S.leaveCafe(), 60 * 3, safe);
  await step('deep fall', 'play|landing|cafe|cafeJump', () => {}, 60 * 90, safe);
  await step('back to falling', 'play', () => { if (M.state === 'cafe') S.leaveCafe(); }, 60 * 4, safe);   // the deep fall may end at a cafe
  // The deep cave at about 20.5 km: he lands, looks about, prises the chest open, and keeps falling through the floor's hole.
  await step('deep cave', 'cave', () => { const K = M.caveInfo(); P.y = K.T - 60; P.x = K.entryX; P.aim = P.x; }, 60 * 13, safe);
  await step('cave keep falling', 'play|cave', () => $('caveFall').click(), 60 * 4, safe);
  await step('death', 'over|dying', () => { P.inv = 0; P.shield = 0; P.hp = 1; M.rocks.length = 0; M.rocks.push({ d: P.y + 14, x0: P.x, x: P.x, size: 1, rr: 9, amp: 0, ph: 0, sp: 1, hot: true, isMine: true, dead: false }); }, 60 * 4);
  await step('high scores', '', () => M.openTable && M.openTable(), 30);
  await step('back to menu', 'title', () => S.toTitle(), 30);
  if (S.wakeWant) out.errors.push('screen awake: still asked for on the menu');
  await step('self-test', 'intro|play', () => S.perfStart(), 60 * 3);
  await step('self-test quit', 'title', () => S.toTitle(), 20);
  if (S.perfOn) out.errors.push('self-test still on after quitting it');
  // The escape preview (five taps on the pilot, then its pop-up): off the record, so the save must come back exactly as it was, whether
  // it ends at the ending, at its game over card, or by Quit from pause.
  const kept = JSON.stringify(M.save);
  const unchanged = how => { if (JSON.stringify(M.save) !== kept) out.errors.push('escape preview changed the save (' + how + ')'); if (S.previewOn) out.errors.push('escape preview still on (' + how + ')'); };
  await step('escape preview asks', 'title', () => S.askPreview(), 10);
  if (!$('confirmDlg').open) out.errors.push('escape preview: no pop-up before it starts');
  await step('escape preview', 'cave', async () => { await wait(900); $('confirmYes').click(); }, 60 * 22, safe);
  await step('preview claim kit', 'cave', () => $('caveClaim').click(), 60 * 8, safe);
  if ($('caveClaim').textContent !== 'Through the portal') out.errors.push('escape preview: no drone card after the kit');
  await step('preview portal', 'launch', () => $('caveClaim').click(), 60 * 8);
  await step('preview ending', 'ended', () => S.showEnd(), 30);
  if (!$('newMissionBtn').hidden) out.errors.push('escape preview ending offers New mission');
  await step('preview to menu', 'title', () => $('endTitleBtn').click(), 30);
  unchanged('ending');
  await step('preview again', 'intro|play', () => S.startPreview(), 60 * 2, safe);
  await step('preview quit', 'title', () => S.toTitle(), 20);
  unchanged('quit');
  await step('preview to die', 'play', () => S.startPreview(), 60 * 2, safe);
  await step('preview death', 'over', () => { P.y = M.caveInfo().T - 1500; P.inv = 0; P.shield = 0; P.hp = 1; M.rocks.length = 0; M.rocks.push({ d: P.y + 14, x0: P.x, x: P.x, size: 1, rr: 9, amp: 0, ph: 0, sp: 1, hot: true, isMine: true, dead: false }); }, 60 * 6);
  await step('preview game over', 'title', () => S.toTitle(), 20);
  unchanged('death');
  await step('launch', 'launch', () => M.startLaunch(), 60 * 20);
  // The back gesture during the launch skips to the end screen (where the mission is counted) instead of leaving.
  await step('back skips the launch', 'ended', () => dispatchEvent(new PopStateEvent('popstate', { state: null })), 10);
  await step('ending', 'launch|ended', () => S.showEnd(), 30);
  await step('menu again', 'title', () => S.toTitle(), 30);
  // ---- Every answer on every card (CODING.md rule 9), then a real cave claim through to the end screen, and the drone
  // flying. These come last: they set the save up as each card needs it (the ship ready or not, the drone not yet his,
  // no mission flown), so nothing before them sees those changes.
  // press() presses one of the confirm card's buttons, as a player would, only if that card is up with that button
  // showing and enabled, and records it as 'kind: label'; tools/smoke.py fails on any of its PRESSES never pressed.
  out.pressed = [];
  const check = (what, ok) => { if (!ok) out.errors.push(what); };
  const dlgOpen = () => $('confirmDlg').open, shown = id => !$(id).hidden;
  const press = (kind, id) => {
    const b = $(id), open = dlgOpen();
    if (!open || S.confirmKind !== kind || b.hidden || b.disabled) {
      out.errors.push("card '" + kind + "': no " + id + ' to press (' + (open ? "card '" + S.confirmKind + "' is up" : 'no card is up') + ')');
      return;
    }
    out.pressed.push(kind + ': ' + b.textContent.trim()); b.click();
  };
  const until = (done, max, keep) => { for (let i = 0; i < max && !done(); i++) run(1, keep); };
  // The ship repaired and every component fitted, or nothing at all, with no components waiting for a cafe's card.
  const shipReady = ready => {
    const sv = M.save;
    sv.compsNew = []; delete sv.partsGift;
    if (ready) { S.fillParts(); sv.compsGot = M.COMPONENTS.map(cp => cp.id); }
    else { for (const id of Object.keys(sv.parts)) sv.parts[id] = 0; sv.compsGot = []; }
    M.renderRepair();
    check('the ship could not be set ' + (ready ? 'ready' : 'unrepaired') + ' for the cards', M.canLaunch() === ready);
  };
  // A quick dive (Fall again), on to cafe 1, landing on its pad and standing at the counter until the menu is due.
  const diveToPlay = () => { S.startRun(true); until(() => M.state === 'play', 60 * 4); };
  const toCafe = () => {
    diveToPlay();
    const C = M.cafeInfo(1); P.y = C.Dl - 400;
    until(() => M.state === 'cafe' && M.cafeT > 1.7, 60 * 10, () => { safe(); P.x = C.padX; P.aim = P.x; });
  };
  // The cafe's menu waits behind a card; once the card is answered it opens.
  const atCafe = (how, menu) => {
    check(how + ': not at the cafe (' + M.state + ')', M.state === 'cafe');
    check(how + ': the card is still up', !dlgOpen());
    check(how + ': the cafe menu ' + (menu ? 'did not open' : 'opened'), shown('shop') === menu);
  };
  autoCard = false;
  // The components card with the ship not ready: one button, Great!, then the cafe menu.
  await step('components card at a cafe', 'cafe', () => { shipReady(false); M.save.compsNew = [M.COMPONENTS[1].id]; toCafe(); }, 0);
  check('components card: not up at the cafe', dlgOpen() && S.confirmKind === 'comps');
  check('components card: Not yet shown while the ship cannot fly', !shown('confirmNo'));
  check('components card: the components were not marked as shown', !M.save.compsNew.length);
  check('components card: the cafe menu opened behind it', !shown('shop'));
  await step('components card Great!', 'cafe', () => press('comps', 'confirmYes'), 10);
  atCafe('components card Great!', true);
  // The components card with the ship ready: Fly home! or Not yet. Not yet leaves the cafe as it was.
  await step('components card, ship ready', 'cafe', () => { S.toTitle(); shipReady(true); M.save.compsNew = [M.COMPONENTS[0].id]; toCafe(); }, 0);
  check('components card (ship ready): not up at the cafe', dlgOpen() && S.confirmKind === 'comps' && shown('confirmNo'));
  await step('components card Not yet', 'cafe', () => press('comps', 'confirmNo'), 10);
  atCafe('components card Not yet', true);
  check('components card Not yet: the ship is no longer ready', M.canLaunch());
  // The cafe's own launch, on its Ship repair card: Not yet stays at the cafe; Fly home! ends the dive there, asks for
  // initials (a top 10 depth), and the launch starts when the high scores close. The drone isn't his yet, so the end
  // screen then tells him it is (tellDroneEnd).
  await step('cafe launch button', 'cafe', () => { S.cafeCard('repair', true); check('cafe: no launch button on the Ship repair card', shown('cafeLaunchBtn')); $('cafeLaunchBtn').click(); }, 10);
  check("cafe launch: no card from the launch button", dlgOpen() && S.confirmKind === 'launch');
  await step('cafe launch Not yet', 'cafe', () => press('launch', 'confirmNo'), 10);
  atCafe('cafe launch Not yet', true);
  await step('cafe launch Fly home!', 'over', () => {
    M.save.droneOpen = false; M.save.drone = false;
    $('cafeLaunchBtn').click(); press('launch', 'confirmYes');
  }, 10);
  check('cafe launch Fly home!: no initials to enter', shown('scoreScreen') && shown('hsEntry') && S.hsFrom === 'launch');
  check('cafe launch Fly home!: the card is still up', !dlgOpen());
  await step('cafe launch scores closed', 'launch', () => $('hsDone').click(), 30);
  await step('cafe launch skipped', 'ended', () => { run(5); dispatchEvent(new PopStateEvent('popstate', { state: null })); }, 10);
  check('cafe launch: the end screen is not showing', shown('endScreen'));
  await step('drone card after the ending', 'ended', () => wait(800), 5);
  check('drone card after the ending: not up', dlgOpen() && S.confirmKind === 'droneEnd' && !shown('confirmNo'));
  check('drone card after the ending: the drone was not unlocked and switched on', M.save.droneOpen === true && M.save.drone === true);
  await step('drone card Great!', 'ended', () => press('droneEnd', 'confirmYes'), 10);
  check('drone card Great!: the card is still up', !dlgOpen());
  check('drone card Great!: the end screen is gone', shown('endScreen'));
  // The components card's Fly home!: the dive ends at the cafe, as with the launch button.
  await step('components card Fly home!', 'over', () => {
    S.toTitle(); shipReady(true); M.save.compsNew = [M.COMPONENTS[0].id]; toCafe();
    press('comps', 'confirmYes');
  }, 10);
  check('components card Fly home!: no initials to enter', shown('scoreScreen') && S.hsFrom === 'launch');
  check('components card Fly home!: the cafe menu is still up', !shown('shop'));
  await step('components card launch', 'launch', () => $('hsDone').click(), 30);
  // The dive that finished the ship: congratulations on the game over card. Later leaves that card as it was, with
  // its own launch button; Fly home! starts the launch.
  const finishShipAndEnd = () => {
    S.toTitle(); shipReady(false); diveToPlay(); shipReady(true); M.gameOver();
    if (shown('scoreScreen')) $('hsDone').click();   // a top 10 depth asks for initials first
  };
  await step('ship repaired card', 'over', finishShipAndEnd, 10);
  check('ship repaired card: not up on the game over card', dlgOpen() && S.confirmKind === 'repaired' && shown('overScreen'));
  await step('ship repaired Later', 'over', () => press('repaired', 'confirmNo'), 10);
  check('ship repaired Later: not back on the game over card with its launch button', !dlgOpen() && shown('overScreen') && shown('overLaunchBtn'));
  await step('ship repaired again', 'over', finishShipAndEnd, 10);
  await step('ship repaired Fly home!', 'launch', () => press('repaired', 'confirmYes'), 30);
  check('ship repaired Fly home!: the card is still up', !dlgOpen());
  // The drone offered at Jump in, for a save that flew home before the drone came with the ending: after Jump in's own
  // card (Dive!), either answer unlocks it and starts the dive; only Yes switches it on.
  const offerDrone = () => {
    S.toTitle(); shipReady(false); M.save.droneOpen = false; M.save.drone = false; M.save.missionsDone = Math.max(1, M.save.missionsDone || 0);
    $('startBtn').click(); press('jump', 'confirmYes');
  };
  await step('drone offered', 'title', offerDrone, 5);
  check('drone offered: no card after Dive!', dlgOpen() && S.confirmKind === 'drone');
  await step('drone Not now', 'intro|play', () => press('drone', 'confirmNo'), 10);
  check('drone Not now: not unlocked and switched off', M.save.droneOpen === true && M.save.drone === false && !M.droneRun && !dlgOpen());
  await step('drone offered again', 'title', offerDrone, 5);
  await step('drone Yes', 'intro|play', () => press('drone', 'confirmYes'), 10);
  check('drone Yes: not unlocked and switched on', M.save.droneOpen === true && M.save.drone === true && M.droneRun && !dlgOpen());
  // The drone on a long fall, past cafe 1 (he leaves it at once) and the Leviathan below it: it must catch some of the
  // parts and crystals he misses. A component's card on the way gets Continue (the ship can't fly, so that's Great!).
  autoCard = true;
  await step('fall with the drone', 'play|landing|cafe|cafeJump', () => {}, 60 * 70, () => { safe(); if (M.state === 'cafe' && !dlgOpen()) S.leaveCafe(); });
  autoCard = false;
  out.droneCaught = M.drone ? M.drone.caught : 0;
  check('fall with the drone: it caught nothing', out.droneCaught > 0);
  // A real (not preview) cave claim: the kit repairs the ship, the chest gives the drone (he hasn't got it) with its
  // own card, the portal ends the dive, a top 10 depth asks for initials (from 'launch'), and the launch and the end
  // screen follow. A first finished mission is counted once and unlocks the suits; the end screen names the drone.
  let cave0 = null;
  await step('cave, for real', 'cave', () => {
    S.toTitle(); shipReady(false);
    Object.assign(M.save, { droneOpen: false, drone: false, droneNew: false, missionsDone: 0, missionDone: false });
    cave0 = { launches: M.save.launches || 0, scores: M.save.scores.length };
    diveToPlay();
    const K = M.caveInfo(); P.y = K.T - 60; P.x = K.entryX; P.aim = P.x;
    until(() => shown('caveUi'), 60 * 15, safe);
  }, 0);
  check('cave: no card with the kit', shown('caveUi') && $('caveClaim').textContent === 'Claim ship repair kit' && shown('caveFall'));
  await step('cave claim kit', 'cave', () => { $('caveClaim').click(); run(5); until(() => shown('caveUi'), 60 * 10, safe); }, 0);
  check('cave claim: no drone card after the kit', shown('caveUi') && $('caveClaim').textContent === 'Through the portal');
  check('cave claim: the ship is not repaired', M.canLaunch());
  check('cave claim: the drone is not his, switched on and waiting to be announced', M.save.droneOpen === true && M.save.drone === true && M.save.droneNew === true);
  await step('cave portal', 'over', () => { $('caveClaim').click(); until(() => M.state !== 'cave', 60 * 10, safe); }, 0);
  const caveM = M.depthM();
  check('cave portal: no initials to enter from the launch', shown('scoreScreen') && shown('hsEntry') && S.hsFrom === 'launch');
  check('cave portal: the best depth was not kept', M.save.best >= caveM);
  await step('cave initials', 'over', () => $('hsSave').click(), 5);
  check('cave initials: the score is not on the table', M.save.scores.length === cave0.scores + 1 && M.save.scores.some(sc => sc.m === caveM));
  await step('cave launch', 'launch', () => $('hsDone').click(), 60 * 3);
  await step('cave ending', 'ended', () => { run(5); dispatchEvent(new PopStateEvent('popstate', { state: null })); }, 10);
  check('cave ending: the mission was not counted once', M.save.missionsDone === 1 && M.save.missionDone === true);
  check('cave ending: the launch was not counted once', M.save.launches === cave0.launches + 1);
  const unlocks = $('eUnlock').textContent;
  check('cave ending: the end screen does not name the suits and the drone (' + unlocks + ')', shown('eUnlock') && unlocks.includes('Every suit colour unlocked') && unlocks.includes('Helper drone unlocked!'));
  check('cave ending: the drone is still waiting to be announced', M.save.droneNew === false);
  check('cave ending: no New mission button', shown('newMissionBtn'));
  await step('cave ending, a moment later', 'ended', () => wait(800), 5);
  check("cave ending: the drone's card came up although the chest gave it", !dlgOpen());
  autoCard = true;
  await step('menu at the end', 'title', () => S.toTitle(), 30);
  out.seen = [...seen];
  const pre = document.createElement('pre'); pre.id = 'out'; pre.textContent = JSON.stringify(out); document.body.appendChild(pre);
})();
</script>"""


def page(game):
    game = chrome.inject(game, test_pages.HOOK + '\n' + HOOK, 'smoke')
    return test_pages.HEAD + same_pixels.SEEDED + chrome.HELPERS + game + DRIVER + '</body></html>'


def run(src, moon):
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, 'smoke.html')
        open(path, 'w', encoding='utf-8').write(page(open(src, encoding='utf-8').read()))
        dom = chrome.dump_dom('file://' + path + '?moon=' + moon, os.path.join(tmp, 'chrome'), 300000, 600, size='390,844')
    return chrome.result(dom)


def main():
    args = sys.argv[1:]
    src = args.pop(0) if args and args[0].endswith('.html') else os.path.join(ROOT, 'src', 'moonfall.html')
    chrome.need_chrome('smoke')
    game = open(src, encoding='utf-8').read()
    moons = args or chrome.moons(game)
    fails = 0
    for moon in moons:
        res = run(src, moon)
        if res is None:
            print(f'FAIL {moon}: the page did not finish (it stopped before the last step)'); fails += 1; continue
        bad = [s for s in res['steps'] if not s['ok']]
        probs = res.get('problems', [])
        for p in probs: print(f'PROBLEM {moon}: {p}')
        for e in res['errors']: print(f'ERROR {moon}: {e}')
        for s in bad: print(f"FAIL {moon}: step '{s['name']}' ended in state '{s['state']}'")
        print(f"{moon}: {len(res['steps'])} steps, {len(res['errors'])} errors, {len(bad)} steps off course, {len(probs)} problems from the game's own checks")
        unseen = sorted(set(re.findall(r"setState\('(\w+)'\)", game)) - set(res.get('seen', [])))
        for st in unseen: print(f"FAIL {moon}: the game can enter state '{st}' but the smoke test never reached it; add a step for it")
        # Fail closed: what a step should have done but didn't (a missing result counts as nothing done).
        unpressed = [p for p in PRESSES if p not in res.get('pressed', [])]
        for p in unpressed: print(f"FAIL {moon}: the card button '{p}' was never pressed")
        want, cards = res.get('compCardsWant', 0), res.get('compCards', 0)
        missing = []
        if not want: missing.append('the smoke test never landed at a cafe with a component to show')
        elif cards < want: missing.append(f'{want} cafe landings had components to show, but only {cards} component cards came up')
        if not res.get('droneCaught'): missing.append('the helper drone caught nothing on its fall')
        for m in missing: print(f'FAIL {moon}: {m}')
        print(f"{moon}: {len(res.get('pressed', []))} card buttons pressed, {cards} component cards, drone caught {res.get('droneCaught', 0)}")
        fails += len(res['errors']) + len(bad) + len(unseen) + len(probs) + len(unpressed) + len(missing)
    print('FAIL: the smoke test found problems (above)' if fails else 'OK: every screen played on every moon, no errors')
    sys.exit(1 if fails else 0)


if __name__ == '__main__':
    main()
