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
