import type { ComponentType } from "react";
import type { Block, BlockVariant } from "../site-content";
import { CTA } from "./CTA";
import { Contact } from "./Contact";
import { FAQ } from "./FAQ";
import { Features } from "./Features";
import { Hero } from "./Hero";
import { Prose } from "./Prose";

export type BlockComponentProps = {
	block: Block;
	anchorID: string;
};

const blockComponents: Record<BlockVariant, ComponentType<BlockComponentProps>> = {
	hero: Hero,
	features: Features,
	prose: Prose,
	cta: CTA,
	faq: FAQ,
	contact: Contact,
};

export function resolveBlockComponent(variant: BlockVariant): ComponentType<BlockComponentProps> {
	return blockComponents[variant] ?? Prose;
}
