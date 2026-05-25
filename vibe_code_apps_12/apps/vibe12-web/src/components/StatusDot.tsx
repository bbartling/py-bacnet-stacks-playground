type Props = {
  status: string;
  title?: string;
};

export function StatusDot({ status, title }: Props) {
  const cls = ["status-dot", `status-${status || "offline"}`].join(" ");
  return <span className={cls} title={title || status} aria-label={title || status} />;
}
