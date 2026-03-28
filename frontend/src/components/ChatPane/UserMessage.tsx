interface Props {
  content: string;
}

export function UserMessage({ content }: Props) {
  return (
    <div className="message user-message">
      {content}
    </div>
  );
}
