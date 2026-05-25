// ══════════════════════════════════════════════════════════
//  SPARKLE'S GAME MAKER — UI
// ══════════════════════════════════════════════════════════

// ── Stars ────────────────────────────────────────────────
(function spawnStars(){
  const container = document.getElementById('stars');
  for(let i=0;i<120;i++){
    const s=document.createElement('div');
    s.className='star';
    s.style.cssText=`left:${Math.random()*100}%;top:${Math.random()*100}%;
      width:${Math.random()*2.5+1}px;height:${Math.random()*2.5+1}px;
      animation-delay:${Math.random()*6}s;animation-duration:${Math.random()*4+3}s`;
    container.appendChild(s);
  }
})();

// ── Session / globals ────────────────────────────────────
const sessionId = Math.random().toString(36).slice(2,10);
let gameUrl = '';
let currentGameName = '';

// ── Voice control ────────────────────────────────────────
let voiceEnabled = true;
document.getElementById('voiceToggle').addEventListener('change', e => {
  voiceEnabled = e.target.checked;
  document.getElementById('voiceHint').style.opacity = voiceEnabled ? '1' : '0.3';
});

// ── Difficulty ───────────────────────────────────────────
const DIFF_MAP = {
  none:   {speed_0:210, speed_max:360, speed_inc:22, win:10, lives:5, obs_interval:2600},
  low:    {speed_0:240, speed_max:410, speed_inc:26, win:12, lives:4, obs_interval:2300},
  medium: {speed_0:280, speed_max:480, speed_inc:32, win:15, lives:3, obs_interval:2000},
  high:   {speed_0:340, speed_max:560, speed_inc:40, win:20, lives:2, obs_interval:1700},
};
let difficulty = DIFF_MAP['none'];

document.getElementById('diffBar').addEventListener('click', e=>{
  const btn = e.target.closest('.diff-btn');
  if(!btn) return;
  document.querySelectorAll('#diffBar .diff-btn').forEach(b=>b.classList.remove('active'));
  btn.classList.add('active');
  difficulty = DIFF_MAP[btn.dataset.diff] || DIFF_MAP['none'];
});

// ── Text input + clear ───────────────────────────────────
const gameInput  = document.getElementById('gameInput');
const inputClear = document.getElementById('inputClear');

gameInput.addEventListener('input', ()=>{
  inputClear.style.display = gameInput.value ? 'flex' : 'none';
});
inputClear.addEventListener('click', ()=>{
  gameInput.value='';
  inputClear.style.display='none';
  gameInput.focus();
});
gameInput.addEventListener('keydown', e=>{
  if(e.key==='Enter') document.getElementById('launchBtn').click();
});

// ── Quick-pick chips ─────────────────────────────────────
document.querySelectorAll('.chip').forEach(chip=>{
  chip.addEventListener('click', ()=>{
    if(chip.dataset.params){
      const params = JSON.parse(chip.dataset.params);
      gameInput.value = params.game_name || chip.textContent.trim();
      inputClear.style.display='flex';
      buildGame(params, false);
    } else {
      gameInput.value = chip.dataset.idea || '';
      inputClear.style.display='flex';
      gameInput.focus();
    }
  });
});

// ── Voice recognition ────────────────────────────────────
const listenBar = document.getElementById('listenBar');
const micBtn    = document.getElementById('micBtn');
let recognition = null;
let isListening = false;

function startVoice(){
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  if(!SR){ alert('Voice not supported in this browser. Please type your idea!'); return; }
  if(isListening){ stopVoice(); return; }

  recognition = new SR();
  recognition.lang = 'en-US';
  recognition.interimResults = true;
  recognition.maxAlternatives = 1;

  recognition.onstart = ()=>{
    isListening=true;
    listenBar.style.display='flex';
    micBtn.classList.add('listening');
  };

  recognition.onresult = e=>{
    const transcript = Array.from(e.results)
      .map(r=>r[0].transcript).join('');
    gameInput.value = transcript;
    inputClear.style.display = transcript ? 'flex' : 'none';
  };

  recognition.onend = ()=>{
    isListening=false;
    listenBar.style.display='none';
    micBtn.classList.remove('listening');
    // Auto-launch if we got something
    if(gameInput.value.trim().length > 3){
      document.getElementById('launchBtn').click();
    }
  };

  recognition.onerror = ()=>{ stopVoice(); };

  recognition.start();
}

function stopVoice(){
  try{ recognition?.stop(); }catch(e){}
  isListening=false;
  listenBar.style.display='none';
  micBtn.classList.remove('listening');
}

micBtn.addEventListener('click', startVoice);

// ── Launch button ────────────────────────────────────────
document.getElementById('launchBtn').addEventListener('click', async ()=>{
  const text = gameInput.value.trim();
  if(!text){ gameInput.focus(); gameInput.classList.add('shake'); setTimeout(()=>gameInput.classList.remove('shake'),500); return; }
  stopVoice();
  await launchFromText(text);
});

async function launchFromText(text){
  // Show loading state in overlay
  gameOverlay.style.display='flex';
  overlayEmoji.textContent='✨';
  overlayMsg.textContent='Understanding your idea…';
  playBtn.style.display='none'; reviewBtn.style.display='none';
  gameSummary.innerHTML='';

  try{
    const resp = await fetch('/extract-params',{
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({transcript: text})
    });
    if(!resp.ok) throw new Error('extract failed');
    const params = await resp.json();
    if(params.game_type && params.character){
      gameOverlay.style.display='none';
      showConfirmation(params, text);
    } else {
      // Enough to try — fill defaults and go
      params.game_type = params.game_type||'runner';
      params.character = params.character||'bunny';
      params.collectible = params.collectible||'stars';
      params.obstacle = params.obstacle||'rocks';
      params.world = params.world||'magic land';
      gameOverlay.style.display='none';
      showConfirmation(params, text);
    }
  }catch(e){
    overlayMsg.textContent='Oops! Try again!';
    setTimeout(()=>{ gameOverlay.style.display='none'; }, 2000);
  }
}

// ── Confirm overlay ───────────────────────────────────────
const confirmOverlay = document.getElementById('confirmOverlay');
const confirmHeard   = document.getElementById('confirmHeard');
const confirmParams  = document.getElementById('confirmParams');

function showConfirmation(params, rawText){
  confirmHeard.textContent = params.understood || rawText || 'Your game idea!';
  confirmParams.innerHTML=`
    <span>🦄 ${params.character||'bunny'}</span>
    <span>⭐ ${params.collectible||'stars'}</span>
    <span>⚡ ${params.obstacle||'rocks'}</span>
    <span>🌍 ${params.world||'magic land'}</span>
  `;
  confirmOverlay.style.display='flex';
  document.getElementById('confirmYes').onclick=()=>{
    confirmOverlay.style.display='none';
    buildGame(params, true);
  };
  document.getElementById('confirmRetry').onclick=()=>{
    confirmOverlay.style.display='none';
    gameInput.focus();
    gameInput.select();
  };
}

// ══════════════════════════════════════════════════════════
//  GAME BUILD
// ══════════════════════════════════════════════════════════
const gameOverlay = document.getElementById('gameOverlay');
const overlayEmoji= document.getElementById('overlayEmoji');
const overlayMsg  = document.getElementById('overlayMsg');
const gameSummary = document.getElementById('gameSummary');
const playBtn     = document.getElementById('playBtn');
const reviewBtn   = document.getElementById('reviewBtn');
const gamePlayer  = document.getElementById('gamePlayer');
const gameFrame   = document.getElementById('gameFrame');

async function buildGame(params, isDream=false){
  const gameType = params.game_type || 'runner';
  const charName = params.character||'bunny';
  const collName = params.collectible||'stars';
  const obsName  = params.obstacle||'rocks';
  const world    = params.world||'rainbow land';
  const charNames= {unicorn:'Unicorn Adventure',bunny:'Bunny Hop',dragon:'Dragon Dash',cat:'Cat Jump'};
  const gameName = params.game_name||(charNames[charName]||charName.charAt(0).toUpperCase()+charName.slice(1)+' Adventure')+'!';

  gameOverlay.style.display='flex';
  overlayEmoji.textContent='🪄';
  overlayMsg.textContent='Making your game…';
  playBtn.style.display='none'; reviewBtn.style.display='none';
  gameSummary.innerHTML='';

  // Generate custom images for non-preset characters
  const CHAR_PNG_MAP  = {unicorn:'/transparent-asset/characters/unicorn.png', bunny:'/transparent-asset/characters/bunny.png', rabbit:'/transparent-asset/characters/bunny.png', dragon:'/transparent-asset/characters/dragon.png', cat:'/transparent-asset/characters/cat.png', kitten:'/transparent-asset/characters/cat.png', fairy:'/transparent-asset/characters/fairy_sparkle.png', sparkle:'/transparent-asset/characters/fairy_sparkle.png', star_kid:'/transparent-asset/characters/star_kid.png'};
  const COLL_PNG_MAP  = {star:'/transparent-asset/collectibles/star.png', stars:'/transparent-asset/collectibles/star.png', coin:'/transparent-asset/collectibles/coin.png', coins:'/transparent-asset/collectibles/coin.png', gem:'/transparent-asset/collectibles/gem.png', gems:'/transparent-asset/collectibles/gem.png', heart:'/transparent-asset/collectibles/heart.png', hearts:'/transparent-asset/collectibles/heart.png', cookie:'/transparent-asset/collectibles/cookie.png', cookies:'/transparent-asset/collectibles/cookie.png'};
  const OBS_PNG_MAP   = {
    rock:'/transparent-asset/obstacles/rock.png', rocks:'/transparent-asset/obstacles/rock.png', boulder:'/transparent-asset/obstacles/rock.png',
    cloud:'/transparent-asset/obstacles/cloud.png', clouds:'/transparent-asset/obstacles/cloud.png',
    spike:'/transparent-asset/obstacles/spike.png', spikes:'/transparent-asset/obstacles/spike.png',
    cactus:'/transparent-asset/obstacles/cactus.png',
    wolf:'/transparent-asset/obstacles/wolf.png',
    fox:'/transparent-asset/obstacles/fox.png',
    hawk:'/transparent-asset/obstacles/hawk.png',
    knight:'/transparent-asset/obstacles/knight.png',
    dog:'/transparent-asset/obstacles/dog.png',
    dark_wizard:'/transparent-asset/obstacles/dark_wizard.png', wizard:'/transparent-asset/obstacles/dark_wizard.png',
    ice_crystal:'/transparent-asset/obstacles/ice_crystal.png', ice:'/transparent-asset/obstacles/ice_crystal.png',
    spider:'/transparent-asset/obstacles/spider.png',
    black_hole:'/transparent-asset/obstacles/black_hole.png', blackhole:'/transparent-asset/obstacles/black_hole.png',
    barrel:'/transparent-asset/obstacles/barrel.png',
    bomb:'/transparent-asset/obstacles/bomb.png',
  };

  function resolvePreset(name, map){
    const n=(name||'').toLowerCase();
    for(const [k,v] of Object.entries(map)) if(n.includes(k)) return v;
    return '';
  }

  let charUrl=resolvePreset(charName,CHAR_PNG_MAP)||null;
  let collUrl=resolvePreset(collName,COLL_PNG_MAP)||null;
  let obsUrl =resolvePreset(obsName, OBS_PNG_MAP)||null;

  if(isDream){
    overlayEmoji.textContent='🎨';
    const imgJobs=[];
    const sid=Math.random().toString(36).slice(2,8);
    if(params.needs_custom_char&&params.custom_char_prompt&&!charUrl)
      imgJobs.push(fetch('/generate-custom-image',{method:'POST',headers:{'Content-Type':'application/json'},
        body:JSON.stringify({prompt:params.custom_char_prompt,filename:`char_${sid}.png`,name:params.character||charName})})
        .then(r=>r.json()).then(d=>{if(d.ok) charUrl=d.url;overlayMsg.textContent='🎨 Drawing your character…';}));
    if(params.needs_custom_coll&&params.custom_coll_prompt&&!collUrl)
      imgJobs.push(fetch('/generate-custom-image',{method:'POST',headers:{'Content-Type':'application/json'},
        body:JSON.stringify({prompt:params.custom_coll_prompt,filename:`coll_${sid}.png`,name:params.collectible||collName})})
        .then(r=>r.json()).then(d=>{if(d.ok) collUrl=d.url;}));
    if(params.needs_custom_obs&&params.custom_obs_prompt&&!obsUrl)
      imgJobs.push(fetch('/generate-custom-image',{method:'POST',headers:{'Content-Type':'application/json'},
        body:JSON.stringify({prompt:params.custom_obs_prompt,filename:`obs_${sid}.png`,name:params.obstacle||obsName})})
        .then(r=>r.json()).then(d=>{if(d.ok) obsUrl=d.url;}));
    if(imgJobs.length) await Promise.all(imgJobs);
  }

  overlayEmoji.textContent='✨';
  overlayMsg.textContent='Building your game…';

  const requirements={
    game_type:gameType, character:charName, collectible:collName,
    obstacle:obsName, world, game_name:gameName, difficulty,
    bg_description: params.bg_description||'',
    voice_on: voiceEnabled,
    ...(charUrl&&{char_url_override:charUrl}),
    ...(collUrl&&{coll_url_override:collUrl}),
    ...(obsUrl&&{obs_url_override:obsUrl}),
  };

  let story = params.story || 'Adventure awaits!';
  let gUrl='';

  try{
    // Skip story API call for presets that already have a baked-in story.
    const gamePromise = fetch('/generate-game', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({requirements,session_id:sessionId})});
    const storyPromise = params.story
      ? Promise.resolve(null)
      : fetch('/generate-story',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({params:requirements})});
    const [gameResp, storyResp] = await Promise.all([gamePromise, storyPromise]);
    if(gameResp.ok){const d=await gameResp.json();gUrl=d.game_url;}
    if(storyResp?.ok){const d=await storyResp.json();story=d.story||story;}
  }catch(e){console.warn('build error',e);}

  if(!gUrl){overlayMsg.textContent='😔 Oops! Try again!';setTimeout(()=>{gameOverlay.style.display='none';},3000);return;}

  gameUrl=gUrl;
  currentGameName=gameName;

  gameSummary.innerHTML=`
    <div class="story-line">"${story}"</div>
    <div>🦄 ${charName} &nbsp;⭐ ${collName} &nbsp;⚡ ${obsName} &nbsp;🌍 ${world}</div>`;
  overlayEmoji.textContent='🎮';
  overlayMsg.textContent='✨ Your game is ready! ✨';
  playBtn.style.display='block';
  reviewBtn.style.display='block';
}

playBtn.addEventListener('click', ()=>{
  gameFrame.src=gameUrl;
  gamePlayer.style.display='flex';
  gameOverlay.style.display='none';
});

document.getElementById('closeGameBtn').addEventListener('click', ()=>{
  gamePlayer.style.display='none';
  gameFrame.src='';
  gameOverlay.style.display='none';
});

// ══════════════════════════════════════════════════════════
//  THREE.JS DEV PATH (magicBtn only)
// ══════════════════════════════════════════════════════════
document.getElementById('magicBtn')?.addEventListener('click', ()=>{
  const text = gameInput.value.trim() || 'a magical adventure game';
  buildThreeJSGame(text);
});

async function buildThreeJSGame(transcript){
  gameOverlay.style.display='flex';
  overlayEmoji.textContent='🪄';
  overlayMsg.textContent='Casting 3D magic… 20–30 seconds…';
  playBtn.style.display='none'; reviewBtn.style.display='none';

  try{
    const resp = await fetch('/generate-threejs-game',{
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({description:transcript, session_id:sessionId})
    });
    const data = await resp.json();
    if(!data.ok) throw new Error(data.error||'generation failed');
    gameUrl=data.game_url;
    currentGameName=transcript.slice(0,60);
    overlayEmoji.textContent='🎮';
    overlayMsg.textContent='✨ 3D game ready! ✨';
    playBtn.style.display='block';
  }catch(e){
    overlayMsg.textContent='Magic fizzled… try again!';
    console.error('3D gen error:',e);
  }
}

// ══════════════════════════════════════════════════════════
//  REVIEW & FIX AGENT
// ══════════════════════════════════════════════════════════
const reviewOverlay  = document.getElementById('reviewOverlay');
const reviewClose    = document.getElementById('reviewClose');
const reviewScore    = document.getElementById('reviewScore');
const reviewHeadline = document.getElementById('reviewHeadline');
const reviewStrengths= document.getElementById('reviewStrengths');
const reviewIssues   = document.getElementById('reviewIssues');
const fixBtn         = document.getElementById('fixBtn');
const playFixedBtn   = document.getElementById('playFixedBtn');
const reviewStatus   = document.getElementById('reviewStatus');

let lastReview   = null;
let fixedGameUrl = null;

const SEV_ORDER = {critical:0, high:1, medium:2, low:3};

reviewBtn.addEventListener('click', openReviewPanel);
reviewClose.addEventListener('click', ()=>{ reviewOverlay.style.display='none'; });
fixBtn.addEventListener('click', applyFixes);
playFixedBtn.addEventListener('click', ()=>{
  if(!fixedGameUrl) return;
  gameFrame.src=fixedGameUrl;
  gamePlayer.style.display='flex';
  reviewOverlay.style.display='none';
  gameOverlay.style.display='none';
});

async function openReviewPanel(){
  if(!gameUrl){ reviewStatus.textContent='No game to review yet.'; return; }
  reviewOverlay.style.display='flex';
  reviewScore.textContent='…';
  reviewHeadline.textContent='Analyzing your game…';
  reviewStrengths.innerHTML='';
  reviewIssues.innerHTML='<div style="color:#a78bfa;text-align:center;padding:20px">👩‍🎨 Maya is reviewing your game…</div>';
  fixBtn.disabled=true;
  playFixedBtn.style.display='none';
  reviewStatus.textContent='';
  fixedGameUrl=null;

  try{
    const htmlResp=await fetch(gameUrl);
    if(!htmlResp.ok) throw new Error('Could not fetch game HTML');
    const gameHtml=await htmlResp.text();
    const resp=await fetch('/review-game',{
      method:'POST', headers:{'Content-Type':'application/json'},
      body:JSON.stringify({game_html:gameHtml, game_name:currentGameName, session_id:sessionId})
    });
    const data=await resp.json();
    if(!data.ok) throw new Error(data.error||'Review failed');
    lastReview=data.review;
    renderReview(lastReview);
    fixBtn.disabled=false;
  }catch(e){
    reviewIssues.innerHTML=`<div style="color:#f87171;padding:16px">❌ Review failed: ${e.message}</div>`;
  }
}

function renderReview(r){
  const sc=r.score||0;
  const scoreColor=sc>=8?'#4ade80':sc>=5?'#fbbf24':'#f87171';
  reviewScore.textContent=sc+'/10';
  reviewScore.style.color=scoreColor;
  reviewHeadline.textContent=r.headline||'';
  const ul=(r.strengths||[]).map(s=>`<li>${s}</li>`).join('');
  reviewStrengths.innerHTML=`<ul>${ul}</ul>`;
  const issues=[...(r.issues||[])].sort((a,b)=>(SEV_ORDER[a.severity]??9)-(SEV_ORDER[b.severity]??9));
  reviewIssues.innerHTML=issues.map(iss=>`
    <div class="issue-card ${iss.severity}">
      <span class="issue-badge">${iss.severity}</span>
      <span class="issue-title">${iss.title}</span>
      <div class="issue-desc">${iss.description}</div>
      <div class="issue-fix">${iss.fix_hint}</div>
    </div>`).join('');
}

async function applyFixes(){
  if(!lastReview||!gameUrl){ reviewStatus.textContent='Nothing to fix.'; return; }
  fixBtn.disabled=true;
  fixBtn.textContent='🔧 Fixing…';
  reviewStatus.textContent='o3 is applying all fixes… this may take 30 seconds…';
  playFixedBtn.style.display='none';

  try{
    const htmlResp=await fetch(gameUrl);
    const gameHtml=await htmlResp.text();
    const resp=await fetch('/fix-game',{
      method:'POST', headers:{'Content-Type':'application/json'},
      body:JSON.stringify({
        game_html:gameHtml, issues:lastReview.issues||[],
        fix_summary:lastReview.fix_summary||'', game_name:currentGameName, session_id:sessionId,
      })
    });
    const data=await resp.json();
    if(!data.ok) throw new Error(data.error||'Fix failed');
    fixedGameUrl=data.game_url;
    gameUrl=fixedGameUrl;
    currentGameName=currentGameName+' (fixed)';
    reviewStatus.textContent=`✅ Fixed! ${data.tokens||'?'} tokens used.`;
    fixBtn.textContent='🔧 Apply All Fixes';
    fixBtn.disabled=false;
    playFixedBtn.style.display='block';
  }catch(e){
    reviewStatus.textContent='❌ Fix failed: '+e.message;
    fixBtn.textContent='🔧 Apply All Fixes';
    fixBtn.disabled=false;
  }
}
