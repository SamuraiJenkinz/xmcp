interface ProfileData {
  id: string;
  name?: string;
  displayName?: string;
  jobTitle?: string;
  department?: string;
  email?: string;
  photo_url?: string;
}

interface Props {
  resultJson: string;
}

export function ProfileCard({ resultJson }: Props) {
  let profile: ProfileData | null = null;
  let parseError = false;

  try {
    profile = JSON.parse(resultJson) as ProfileData;
  } catch {
    parseError = true;
  }

  if (parseError || profile === null) {
    return (
      <div className="profile-card">
        <span className="tool-panel-label">Unable to display profile</span>
      </div>
    );
  }

  const displayName = profile.displayName ?? profile.name ?? '';
  const photoSrc = '/api/photo/' + profile.id + '?name=' + encodeURIComponent(displayName);

  return (
    <div className="profile-card">
      <img
        className="profile-card-photo"
        src={photoSrc}
        alt={displayName}
        onError={(e) => {
          (e.currentTarget as HTMLImageElement).style.display = 'none';
        }}
      />
      <div className="profile-card-info">
        {displayName && <div className="profile-card-name">{displayName}</div>}
        {profile.jobTitle && <div className="profile-card-field">{profile.jobTitle}</div>}
        {profile.department && <div className="profile-card-dept">{profile.department}</div>}
        {profile.email && (
          <div className="profile-card-email">
            <a href={`mailto:${profile.email}`}>{profile.email}</a>
          </div>
        )}
      </div>
    </div>
  );
}
