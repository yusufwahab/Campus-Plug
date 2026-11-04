import { policies } from "./content";
import { serverApiOrNull } from "./server-api";
import type { Block } from "./content";

type Slug = keyof typeof policies;

/** Policy text: the Admin-published version when one exists, otherwise the starter copy. */
export async function loadPolicy(slug: Slug): Promise<{ title: string; intro: string; blocks: Block[] }> {
  const starter = policies[slug];
  const live = await serverApiOrNull<{ body: string | null }>(`/policies/${slug}`);
  if (!live?.body) return starter;
  const paragraphs = live.body.split(/\n{2,}/).map((p) => p.trim()).filter(Boolean);
  return { title: starter.title, intro: starter.intro, blocks: [{ heading: "", body: paragraphs }] };
}
