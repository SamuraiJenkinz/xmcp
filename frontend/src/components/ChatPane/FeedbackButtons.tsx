import { useState } from 'react';
import {
  bundleIcon,
  ThumbLikeFilled,
  ThumbLikeRegular,
  ThumbDislikeFilled,
  ThumbDislikeRegular,
} from '@fluentui/react-icons';
import {
  Button,
  Popover,
  PopoverTrigger,
  PopoverSurface,
  Textarea,
} from '@fluentui/react-components';
import { submitFeedback } from '../../api/feedback.ts';
import { useChat } from '../../contexts/ChatContext.tsx';

const ThumbLikeIcon = bundleIcon(ThumbLikeFilled, ThumbLikeRegular);
const ThumbDislikeIcon = bundleIcon(ThumbDislikeFilled, ThumbDislikeRegular);

interface Props {
  threadId: number;
  messageIndex: number; // assistant-message ordinal (0-based)
}

export function FeedbackButtons({ threadId, messageIndex }: Props) {
  const { feedbackMap, dispatch } = useChat();
  const vote = feedbackMap[messageIndex] ?? null;

  const [commentOpen, setCommentOpen] = useState(false);
  const [comment, setComment] = useState('');
  const [announcement, setAnnouncement] = useState('');

  function announce(msg: string) {
    setAnnouncement(msg);
    setTimeout(() => setAnnouncement(''), 1500);
  }

  async function handleThumbUp() {
    if (vote === 'up') {
      // Retract
      dispatch({ type: 'SET_FEEDBACK_VOTE', messageIndex, vote: null });
      await submitFeedback(threadId, messageIndex, null, null);
    } else {
      dispatch({ type: 'SET_FEEDBACK_VOTE', messageIndex, vote: 'up' });
      await submitFeedback(threadId, messageIndex, 'up', null);
      announce('Feedback submitted');
    }
  }

  async function handleThumbDown() {
    if (vote === 'down') {
      // Retract
      dispatch({ type: 'SET_FEEDBACK_VOTE', messageIndex, vote: null });
      setCommentOpen(false);
      await submitFeedback(threadId, messageIndex, null, null);
    } else {
      dispatch({ type: 'SET_FEEDBACK_VOTE', messageIndex, vote: 'down' });
      setCommentOpen(true);
    }
  }

  async function handleCommentSubmit() {
    await submitFeedback(threadId, messageIndex, 'down', comment || null);
    setCommentOpen(false);
    setComment('');
    announce('Feedback submitted');
  }

  async function handleCommentDismiss() {
    // Persist thumbs-down without comment when popover is dismissed without submitting
    await submitFeedback(threadId, messageIndex, 'down', null);
    setCommentOpen(false);
    setComment('');
    announce('Feedback submitted');
  }

  return (
    <>
      <span className="feedback-scale-btn">
        <Button
          appearance="subtle"
          size="small"
          icon={<ThumbLikeIcon filled={vote === 'up'} />}
          onClick={handleThumbUp}
          aria-label={vote === 'up' ? 'Retract thumbs up' : 'Thumbs up'}
          aria-pressed={vote === 'up'}
        />
      </span>
      <Popover
        open={commentOpen}
        onOpenChange={(_, d) => {
          if (!d.open) {
            void handleCommentDismiss();
          }
        }}
        positioning="above-start"
        trapFocus
      >
        <PopoverTrigger disableButtonEnhancement>
          <span className="feedback-scale-btn">
            <Button
              appearance="subtle"
              size="small"
              icon={<ThumbDislikeIcon filled={vote === 'down'} />}
              onClick={handleThumbDown}
              aria-label={vote === 'down' ? 'Retract thumbs down' : 'Thumbs down'}
              aria-pressed={vote === 'down'}
            />
          </span>
        </PopoverTrigger>
        <PopoverSurface>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', minWidth: '240px' }}>
            <Textarea
              placeholder="What went wrong? (optional)"
              value={comment}
              onChange={(_, d) => setComment(d.value.slice(0, 500))}
              resize="vertical"
              maxLength={500}
            />
            <div style={{ display: 'flex', gap: '8px', justifyContent: 'flex-end' }}>
              <Button
                appearance="subtle"
                size="small"
                onClick={() => {
                  void handleCommentDismiss();
                }}
              >
                Cancel
              </Button>
              <Button
                appearance="primary"
                size="small"
                onClick={() => {
                  void handleCommentSubmit();
                }}
              >
                Submit
              </Button>
            </div>
          </div>
        </PopoverSurface>
      </Popover>
      <span
        role="status"
        aria-live="polite"
        aria-atomic="true"
        className="sr-only"
      >
        {announcement}
      </span>
    </>
  );
}
