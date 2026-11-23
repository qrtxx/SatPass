const EARTH_MU = 398600.4418 // km³/s², Earth's gravitational parameter
const EARTH_RADIUS_KM = 6378.137

// Lowest and highest height above Earth, from mean motion (revolutions/day) and eccentricity.
export function orbitShape(sat) {
  const n = (sat.MEAN_MOTION * 2 * Math.PI) / 86400 // rad/s
  const a = Math.cbrt(EARTH_MU / (n * n)) // semi-major axis, km
  return {
    perigeeKm: a * (1 - sat.ECCENTRICITY) - EARTH_RADIUS_KM,
    apogeeKm: a * (1 + sat.ECCENTRICITY) - EARTH_RADIUS_KM,
  }
}

export const formatLat = (deg) => `${Math.abs(deg).toFixed(2)}° ${deg >= 0 ? 'N' : 'S'}`
export const formatLon = (deg) => `${Math.abs(deg).toFixed(2)}° ${deg >= 0 ? 'E' : 'W'}`
