/** Map identity includes the lighting state; immutable revisions hold pixels. */
export function catalogMaps(catalog) {
  return catalog.levels.flatMap(level => {
    const {variants, ...base} = level;
    return (variants?.length ? variants.map(v => ({...base, ...v})) : [base])
      .map(map => ({...map, variant:map.variant || 'day', revision:map.revision || catalog.revision}));
  });
}

export function mapFor(maps, level, variant) {
  const candidates = maps.filter(map => map.level === level);
  return candidates.find(map => map.variant === variant)
    || candidates.find(map => map.variant === 'fixed')
    || candidates.find(map => map.variant === 'day') || candidates[0];
}

export function lightingStates(maps, level) {
  return ['day', 'night'].filter(variant => maps.some(map => map.level === level && map.variant === variant));
}

export function hourFromTime(value) {
  if(value==='night')return 1;
  if(value==='day'||value==null)return 12;
  const m=/^(\d{2}):00$/.exec(value);
  return m&&Number(m[1])<24?Number(m[1]):null;
}

export function hourLabel(hour) { return String(hour).padStart(2,'0')+':00'; }

export function hourFromDialPoint(x,y) {
  if(!Number.isFinite(x)||!Number.isFinite(y)||Math.hypot(x,y)<.12)return null;
  const angle=(Math.atan2(x,-y)+Math.PI*2)%(Math.PI*2);
  return Math.round(angle*12/Math.PI)%24;
}

export function clockFor(maps,level) {
  return maps.find(m=>m.level===level&&m.clock?.step_minutes===60)?.clock;
}

export function mapAtHour(maps,level,hour) {
  const clock=clockFor(maps,level);
  if(!clock)return mapFor(maps,level,hour===1?'night':'day');
  const target=clock.hours.find(h=>h.hour===hour);
  return target&&maps.find(m=>m.level===level&&m.variant===target.variant);
}

/** Preserve a world point when edition crops have different projected bounds. */
export function offsetForBounds(x,y,scale,previous,next) {
  return {x:x+(next[0]-previous[0])*scale,y:y+(next[1]-previous[1])*scale};
}

export function editionFromQuery(value) { return value==='retail'?'retail':'july'; }
