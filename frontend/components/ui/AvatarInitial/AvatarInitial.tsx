import styles from "./AvatarInitial.module.css";

export interface AvatarInitialProps {
  initial: string;
  size?: 32 | 40 | 48 | 56 | 64 | 72;
}

/**
 * design/design-system.md §3 AvatarInitial. Display-only, no interactive
 * states. Font size scales roughly with the avatar's own size rather than a
 * fixed token, since it must always fit one character centered at sizes
 * from 32-72px.
 */
export function AvatarInitial({ initial, size = 40 }: AvatarInitialProps) {
  return (
    <span
      className={styles.avatar}
      style={{ width: size, height: size, fontSize: Math.round(size * 0.45) }}
      aria-hidden="true"
    >
      {initial.slice(0, 1).toUpperCase()}
    </span>
  );
}
