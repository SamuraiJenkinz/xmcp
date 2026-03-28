interface SearchResult {
  name?: string;
  jobTitle?: string;
  department?: string;
  email?: string;
}

interface SearchData {
  results: SearchResult[];
}

interface Props {
  resultJson: string;
}

export function SearchResultCard({ resultJson }: Props) {
  let data: SearchData | null = null;
  let parseError = false;

  try {
    data = JSON.parse(resultJson) as SearchData;
  } catch {
    parseError = true;
  }

  if (parseError || data === null) {
    return (
      <div className="search-results">
        <span className="tool-panel-label">Unable to display search results</span>
      </div>
    );
  }

  if (!data.results || data.results.length === 0) {
    return (
      <div className="search-results">
        <span className="tool-panel-label">No results found</span>
      </div>
    );
  }

  return (
    <div className="search-results">
      {data.results.map((item, idx) => (
        <div key={idx} className="search-result-card">
          {item.name && <span className="search-result-name">{item.name}</span>}
          {item.jobTitle && (
            <>
              <span className="search-result-sep">·</span>
              <span className="search-result-title">{item.jobTitle}</span>
            </>
          )}
          {item.department && (
            <>
              <span className="search-result-sep">·</span>
              <span className="search-result-dept">{item.department}</span>
            </>
          )}
          {item.email && (
            <div className="search-result-email-row">
              <a className="search-result-email" href={`mailto:${item.email}`}>{item.email}</a>
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
