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

export function clockFor(maps,level) {
  return maps.find(m=>m.level===level&&m.clock?.step_minutes===60)?.clock;
}

export function mapAtHour(maps,level,hour) {
  const clock=clockFor(maps,level);
  if(!clock)return mapFor(maps,level,hour===1?'night':'day');
  const target=clock.hours.find(h=>h.hour===hour);
  return target&&maps.find(m=>m.level===level&&m.variant===target.variant);
}
