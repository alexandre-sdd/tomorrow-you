export default function clsx(...values: Array<string | undefined | false>): string {
  return values.filter(Boolean).join(" ");
}
