import './ResultsList.css';

// `null` = no Mars site selected; [] = selected site with no available matches.
// The parent passes results already sorted and ranked by the matching algorithm.
export default function ResultsList({ results = null, selectedRank = null, onSelect }) {
  if (results === null || results === undefined) {
    return (
      <div className="earth-results-empty" role="status">
        <h3>Choose a Mars location</h3>
        <p>Select a site on the Mars map to discover its best Earth analogs.</p>
      </div>
    );
  }

  if (results.length === 0) {
    return (
      <div className="earth-results-empty" role="status">
        <h3>No Earth matches available</h3>
        <p>Polar sites are shown for context only and do not receive Earth recommendations.</p>
        <p>Other sites may also have no results when matching data is unavailable.</p>
      </div>
    );
  }

  return (
    <div className="earth-results">
      <div className="earth-results-heading">
        <h3>Top Earth analogs</h3>
        <span>{results.length} ranked locations</span>
      </div>

      <ol className="earth-results-items" aria-label="Ranked Earth analog locations">
        {results.map((result) => {
          const selected = selectedRank === result.rank;
          const lat = `${Math.abs(result.lat).toFixed(2)}° ${result.lat < 0 ? 'S' : 'N'}`;
          const lon = `${Math.abs(result.lon).toFixed(2)}° ${result.lon < 0 ? 'W' : 'E'}`;

          return (
            <li key={result.id}>
              <button
                type="button"
                className={`earth-results-item${selected ? ' is-selected' : ''}`}
                aria-pressed={selected}
                onClick={() => onSelect?.(result)}
              >
                <span className="earth-results-rank" aria-hidden="true">{result.rank}</span>
                <span className="earth-results-info">
                  <span className="earth-results-name">Earth Analog №{result.rank}</span>
                  <span className="earth-results-coordinates">{lat}, {lon}</span>
                </span>
                <span className="earth-results-score">
                  <strong>{Number.isFinite(result.score) ? result.score.toFixed(1) : 'n/a'}</strong>
                  <span>Match score</span>
                </span>
              </button>
            </li>
          );
        })}
      </ol>

      <p className="earth-results-note">
        Match scores are relative ranking values, not percentages of similarity to Mars.
      </p>
    </div>
  );
}
