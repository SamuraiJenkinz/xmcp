interface Props {
  content: string;
  timestamp?: string;
}

export function UserMessage({ content, timestamp }: Props) {
  return (
    <div className="message user-message">
      {content}
    </div>
  );
}
