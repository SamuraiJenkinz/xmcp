import { useState } from 'react';

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

function getInitials(name: string): string {
  const parts = name.trim().split(/\s+/);
  if (parts.length >= 2) return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
  return name.trim().charAt(0).toUpperCase() || '?';
}

export function ProfileCard({ resultJson }: Props) {
  const [photoFailed, setPhotoFailed] = useState(false);

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
  const photoSrc = profile.photo_url
    ? profile.photo_url + '?name=' + encodeURIComponent(displayName)
    : null;

  return (
    <div className="profile-card">
      {(!photoSrc || photoFailed) ? (
        <div className="profile-card-photo profile-card-initials">
          {getInitials(displayName)}
        </div>
      ) : (
        <img
          className="profile-card-photo"
          src={photoSrc}
          alt={displayName}
          onError={() => setPhotoFailed(true)}
        />
      )}
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
