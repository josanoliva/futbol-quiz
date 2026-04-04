type AffiliateItem = {
  id: string;
  title: string;
  description: string;
  url: string;
  cta: string;
};

type AffiliateBlockProps = {
  title: string;
  description: string;
  items: AffiliateItem[];
};

export default function AffiliateBlock({
  title,
  description,
  items,
}: AffiliateBlockProps) {
  return (
    <section className="rounded-3xl border border-slate-800 bg-slate-900 p-6 shadow-lg">
      <p className="mb-3 text-sm uppercase tracking-widest text-amber-400">
        Recomendado
      </p>
      <h2 className="mb-2 text-2xl font-bold">{title}</h2>
      <p className="mb-6 text-slate-300">{description}</p>

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {items.map((item) => (
          <article
            key={item.id}
            className="rounded-2xl border border-slate-800 bg-slate-950 p-4"
          >
            <h3 className="mb-2 text-lg font-semibold">{item.title}</h3>
            <p className="mb-4 text-sm text-slate-300">{item.description}</p>
            <a
              href={item.url}
              target="_blank"
              rel="nofollow sponsored noopener noreferrer"
              className="inline-block rounded-2xl bg-amber-400 px-4 py-2 font-semibold text-slate-950 hover:bg-amber-300"
            >
              {item.cta}
            </a>
          </article>
        ))}
      </div>
    </section>
  );
}