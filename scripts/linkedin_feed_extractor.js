// LinkedIn feed hiring-post extractor — injected via Playwright browser_evaluate.
// Returns JSON array of hiring-signal posts found in the currently rendered feed.
() => {
  const SIGNALS = /(we'?re hiring|we are hiring|join (my|our) team|is hiring|are hiring|hiring for|looking for (great |strong )?candidates|my team is looking|open (roles?|positions?|reqs?)|new (role|opening)|join us|we'?re (growing|scaling)|now hiring|dm me and|apply (here|now)|careers? page|job (opening|req)|hiring managers?)/i;
  const ROLES = /(ML|machine learning|\bAI\b|LLM|research engineer|applied scientist|data scient|inference|agentic|deep learning|software engineer|SWE|backend|platform|vision|robotics)/i;
  const out = [];
  for (const h2 of [...document.querySelectorAll('main h2')].filter(h => h.textContent.trim() === 'Feed post')) {
    const root = h2.closest('li') || h2.closest('div.feed-shared-update-v2') || h2.parentElement;
    if (!root) continue;
    const fullText = root.innerText || '';
    if (/^Promoted/m.test(fullText) || /Jobs recommended for you/.test(fullText)) continue;
    const lines = fullText.split('\n').map(l => l.trim()).filter(Boolean);
    let poster = '', degree = '', headline = '', time = '', extUrl = '';
    for (let i = 0; i < lines.length; i++) {
      const l = lines[i];
      if (/^(Feed post|View|Add |Send|Like|Comment|Repost|Follow$|•|Recommended|Suggested)/.test(l)) continue;
      if (/reposted this|likes this/.test(l)) continue;
      if (/^\d+[smhdw]/.test(l)) continue;
      const nxt = lines[i + 1] || '';
      if (/^•\s*(1st|2nd|3rd|Following)/.test(nxt)) {
        poster = l; degree = nxt.replace(/^•\s*/, '');
        headline = (lines[i + 2] && !/^•|^\d+[smhdw]|^Follow$|^View my/.test(lines[i + 2])) ? lines[i + 2] : '';
        break;
      }
      if (/^\d+[smhdw]\s*•/.test(nxt)) { poster = l; headline = lines[i + 1] || ''; break; }
    }
    // poster profile url: first /in/ link whose <p> text equals poster name
    for (const a of root.querySelectorAll('a[href*="/in/"]')) {
      const ps = a.querySelectorAll('p');
      if (ps.length && ps[0].textContent.trim() === poster) { extUrl = undefined; posterUrl = a.href.split('?')[0]; break; }
    }
    const tm = fullText.match(/(\d+[smhdw])\s*•/); time = tm ? tm[1] : '';
    let urn = '';
    const dm = root.innerHTML.match(/activity(?:%3A|:)(\d{15,})/);
    if (dm) urn = dm[1];
    let linkUrl = '';
    for (const a of root.querySelectorAll('a[href*="safety/go"]')) {
      try { const u = new URL(a.href).searchParams.get('url'); if (u && !u.includes('lnkd.in')) { linkUrl = u; break; } } catch {}
    }
    const timeIdx = lines.findIndex(l => /^\d+[smhdw]\s*•/.test(l));
    const bodyLines = timeIdx >= 0 ? lines.slice(timeIdx + 1).filter(l => !/^(Follow$|… more|\d+$|Send$|Comment$|Repost$|Like$|reaction|Starting a new position)/.test(l)) : [];
    const body = bodyLines.join('\n');
    if (!SIGNALS.test(body)) continue;
    out.push({
      poster, posterUrl, degree, headline: headline.slice(0, 200), time, urn,
      role_match: ROLES.test(body + ' ' + headline),
      body: body.slice(0, 1200), link_url: linkUrl,
      post_url: urn ? `https://www.linkedin.com/feed/update/urn:li:activity:${urn}/` : ''
    });
  }
  return out;
}
