import { useState, useCallback } from 'react';
import {
  Card,
  Title3,
  Body1,
  Subtitle2,
  Button,
  makeStyles,
  tokens,
} from '@fluentui/react-components';
import {
  ShieldKeyhole24Regular,
  Copy16Regular,
  Checkmark16Regular,
  Mail24Regular,
} from '@fluentui/react-icons';

const ADMIN_EMAIL = (import.meta.env.VITE_ADMIN_EMAIL as string) || 'it-admin@mercer.com';

interface Props {
  upn: string | null;
}

const useStyles = makeStyles({
  root: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    minHeight: '100vh',
    backgroundColor: tokens.colorNeutralBackground1,
    padding: tokens.spacingHorizontalL,
  },
  card: {
    maxWidth: '480px',
    width: '100%',
    padding: tokens.spacingVerticalXXL,
    textAlign: 'center',
  },
  icon: {
    fontSize: '48px',
    color: tokens.colorPaletteRedForeground1,
    marginBottom: tokens.spacingVerticalL,
  },
  title: {
    marginBottom: tokens.spacingVerticalM,
  },
  body: {
    marginBottom: tokens.spacingVerticalL,
    color: tokens.colorNeutralForeground2,
  },
  upnRow: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    gap: tokens.spacingHorizontalS,
    marginBottom: tokens.spacingVerticalL,
    fontFamily: tokens.fontFamilyMonospace,
  },
  actions: {
    display: 'flex',
    flexDirection: 'column',
    gap: tokens.spacingVerticalS,
    alignItems: 'center',
  },
});

export function AccessDenied({ upn }: Props) {
  const styles = useStyles();
  const [copied, setCopied] = useState(false);

  const handleCopyUpn = useCallback(() => {
    if (!upn) return;
    navigator.clipboard.writeText(upn).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    }).catch((err) => {
      console.error('Failed to copy UPN:', err);
    });
  }, [upn]);

  const subject = encodeURIComponent('Atlas Access Request');
  const body = encodeURIComponent(
    `Hi,\n\nI'd like access to Atlas.\n\nMy UPN is: ${upn ?? '(unknown)'}\n\nThank you.`
  );
  const mailtoHref = `mailto:${ADMIN_EMAIL}?subject=${subject}&body=${body}`;

  return (
    <div className={styles.root}>
      <Card className={styles.card}>
        <ShieldKeyhole24Regular className={styles.icon} aria-hidden="true" />
        <Title3 className={styles.title}>Access Denied</Title3>
        <Body1 className={styles.body}>
          You are signed in but do not have the required role to use Atlas.
          Contact your administrator to request access.
        </Body1>

        {upn && (
          <div className={styles.upnRow}>
            <Subtitle2>Your identity:</Subtitle2>
            <Body1>{upn}</Body1>
            <Button
              size="small"
              appearance="subtle"
              icon={copied ? <Checkmark16Regular /> : <Copy16Regular />}
              onClick={handleCopyUpn}
              aria-label={copied ? 'Copied' : 'Copy your identity to clipboard'}
            />
          </div>
        )}

        <div className={styles.actions}>
          <Button
            appearance="primary"
            icon={<Mail24Regular />}
            as="a"
            href={mailtoHref}
          >
            Request Access
          </Button>
        </div>
      </Card>
    </div>
  );
}
