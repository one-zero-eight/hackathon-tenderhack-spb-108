import { useState, type FormEvent } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { ChevronDown, LoaderCircle, Search } from "lucide-react";
import { $api } from "../api";
import exampleSearchResultsRaw from "../../example.json?raw";
import { Button } from "../components/ui/button";
import type {
  SchemaSearchResults,
  SchemaSearchSource,
} from "../api/openapi.gen";
import { regions, ALL_REGIONS } from "@/lib/regions";

export const Route = createFileRoute("/")({ component: Home });

type Product = {
  title: string;
  image: string | null;
  characteristics: string[];
  productLink?: string | null;
  price?: string | null;
  rating?: string | null;
  reviews?: string | null;
};

type MarketplaceGroup = {
  title: string;
  logoUrl: string;
  sourceUrl: string;
  products: Product[];
};

const CHARACTERISTICS_PREVIEW_LIMIT = 5;
const PRODUCTS_PER_PAGE = 3;

function RegionDropdown({
  selectedRegion,
  onSelect,
}: {
  selectedRegion: string;
  onSelect: (region: string) => void;
}) {
  const [isOpen, setIsOpen] = useState(false);

  return (
    <div className="relative flex flex-col gap-2">
      <span className="text-sm font-medium text-slate-700">Выбор региона</span>
      <button
        aria-expanded={isOpen}
        className="flex h-11 w-full items-center justify-between gap-3 rounded-md border border-slate-300 bg-white px-3 text-left text-sm outline-none transition focus:border-slate-900 focus:ring-2 focus:ring-slate-900/10"
        onClick={() => setIsOpen((current) => !current)}
        type="button"
      >
        <span className="truncate">{selectedRegion}</span>
        <ChevronDown
          aria-hidden="true"
          className={`size-4 shrink-0 text-slate-500 transition ${
            isOpen ? "rotate-180" : ""
          }`}
        />
      </button>

      {isOpen ? (
        <div className="absolute left-0 right-0 top-full z-20 mt-2 max-h-72 overflow-y-auto rounded-md border border-slate-200 bg-white py-1 shadow-lg">
          {regions.map((region, index) => (
            <button
              className={`block w-full px-3 py-2 text-left text-sm transition hover:bg-slate-100 ${
                region === selectedRegion
                  ? "font-medium text-slate-950"
                  : "text-slate-700"
              } ${
                index === 0
                  ? "sticky top-0 z-10 border-b border-slate-200 bg-white"
                  : ""
              }`}
              key={region}
              onClick={() => {
                onSelect(region);
                setIsOpen(false);
              }}
              type="button"
            >
              {region}
            </button>
          ))}
        </div>
      ) : null}
    </div>
  );
}

function ProductCharacteristics({
  characteristics,
}: {
  characteristics: string[];
}) {
  const [showAll, setShowAll] = useState(false);
  const visibleCharacteristics = showAll
    ? characteristics
    : characteristics.slice(0, CHARACTERISTICS_PREVIEW_LIMIT);
  const hasHiddenCharacteristics =
    characteristics.length > CHARACTERISTICS_PREVIEW_LIMIT;

  if (characteristics.length === 0) {
    return null;
  }

  return (
    <div className="flex flex-col gap-2">
      <ul className="space-y-1 text-sm text-slate-600">
        {visibleCharacteristics.map((characteristic) => (
          <li
            className="border-l border-slate-200 pl-3 leading-5"
            key={characteristic}
          >
            {characteristic}
          </li>
        ))}
      </ul>
      {!showAll && hasHiddenCharacteristics ? (
        <button
          className="self-start text-sm font-medium text-slate-900 underline underline-offset-2 transition hover:text-slate-600 focus:outline-none focus:ring-2 focus:ring-slate-900/10"
          onClick={() => setShowAll(true)}
          type="button"
        >
          Показать все
        </button>
      ) : null}
      {showAll && hasHiddenCharacteristics ? (
        <button
          className="self-start text-sm font-medium text-slate-900 underline underline-offset-2 transition hover:text-slate-600 focus:outline-none focus:ring-2 focus:ring-slate-900/10"
          onClick={() => setShowAll(false)}
          type="button"
        >
          Скрыть
        </button>
      ) : null}
    </div>
  );
}

function ProductSourceDetails({ group }: { group: MarketplaceGroup }) {
  const [page, setPage] = useState(0);
  const pageCount = Math.ceil(group.products.length / PRODUCTS_PER_PAGE);
  const currentPage = Math.min(page, Math.max(pageCount - 1, 0));
  const visibleProducts = group.products.slice(
    currentPage * PRODUCTS_PER_PAGE,
    (currentPage + 1) * PRODUCTS_PER_PAGE,
  );
  const canPaginate = pageCount > 1;

  return (
    <details
      className="group rounded-lg border border-slate-200 bg-white shadow-sm"
      open
    >
      <summary className="flex cursor-pointer list-none flex-col gap-4 px-4 py-4 marker:hidden sm:flex-row sm:items-center sm:justify-between">
        <span className="flex min-w-0 items-center gap-3 self-stretch sm:self-auto">
          <img
            alt=""
            className="size-10 shrink-0 rounded-md border border-slate-200 bg-white object-contain p-1"
            loading="lazy"
            src={group.logoUrl}
          />
          <span className="min-w-0">
            <span className="block truncate text-base font-semibold text-slate-950">
              {group.title}
            </span>
          </span>
        </span>
        <span className="flex items-center justify-between gap-3 self-stretch sm:shrink-0 sm:self-auto">
          <a
            className="rounded-md border border-slate-300 bg-white px-3 py-1.5 text-center text-sm font-medium text-slate-800 transition hover:bg-slate-100 focus:outline-none focus:ring-2 focus:ring-slate-900/10"
            href={group.sourceUrl}
            onClick={(event) => event.stopPropagation()}
            rel="noreferrer"
            target="_blank"
          >
            Перейти на маркетплейс
          </a>
          <span className="rounded-full border border-slate-200 px-3 py-1 text-sm text-slate-600">
            {group.products.length}
          </span>
        </span>
      </summary>

      <div className="border-t border-slate-200 p-4">
        {group.products.length > 0 ? (
          <div className="flex flex-col gap-4">
            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
              {visibleProducts.map((product) => (
                <article
                  className="overflow-hidden rounded-lg border border-slate-200 bg-white"
                  key={`${product.title}-${product.productLink ?? ""}`}
                >
                  {product.image ? (
                    <img
                      alt={product.title}
                      className="h-44 w-full object-cover"
                      loading="lazy"
                      src={product.image}
                    />
                  ) : (
                    <div className="flex h-44 items-center justify-center bg-slate-100 text-sm text-slate-500">
                      Нет изображения
                    </div>
                  )}
                  <div className="flex flex-col gap-3 p-4">
                    {product.productLink ? (
                      <a
                        className="line-clamp-2 text-base font-semibold leading-6 text-slate-950 transition hover:text-slate-700 focus:outline-none focus:ring-2 focus:ring-slate-900/10"
                        href={product.productLink}
                        rel="noreferrer"
                        target="_blank"
                      >
                        {product.title}
                      </a>
                    ) : (
                      <h3 className="line-clamp-2 text-base font-semibold leading-6 text-slate-950">
                        {product.title}
                      </h3>
                    )}
                    {product.price ? (
                      <p className="text-sm font-medium text-slate-900">
                        {product.price} ₽
                      </p>
                    ) : null}
                    {product.rating || product.reviews ? (
                      <p className="text-sm text-slate-600">
                        {[
                          product.rating ? `${product.rating} ★` : null,
                          product.reviews,
                        ]
                          .filter(Boolean)
                          .join(" · ")}
                      </p>
                    ) : null}
                    <ProductCharacteristics
                      characteristics={product.characteristics}
                    />
                  </div>
                </article>
              ))}
            </div>
            {canPaginate ? (
              <div className="flex items-center justify-center gap-3">
                <button
                  className="rounded-md border border-slate-300 bg-white px-3 py-1.5 text-sm font-medium text-slate-800 transition hover:bg-slate-100 disabled:cursor-not-allowed disabled:opacity-50"
                  disabled={currentPage === 0}
                  onClick={() => setPage((current) => Math.max(current - 1, 0))}
                  type="button"
                >
                  Назад
                </button>
                <span className="text-sm text-slate-600">
                  {currentPage + 1} / {pageCount}
                </span>
                <button
                  className="rounded-md border border-slate-300 bg-white px-3 py-1.5 text-sm font-medium text-slate-800 transition hover:bg-slate-100 disabled:cursor-not-allowed disabled:opacity-50"
                  disabled={currentPage >= pageCount - 1}
                  onClick={() =>
                    setPage((current) => Math.min(current + 1, pageCount - 1))
                  }
                  type="button"
                >
                  Вперёд
                </button>
              </div>
            ) : null}
          </div>
        ) : (
          <p className="rounded-md bg-slate-50 px-4 py-6 text-center text-sm text-slate-500">
            Ничего не найдено по текущему запросу.
          </p>
        )}
      </div>
    </details>
  );
}

function mapSearchSourceToGroup(source: SchemaSearchSource): MarketplaceGroup {
  return {
    title: source.source_title,
    logoUrl:
      source.source_favicon_url ??
      `https://www.google.com/s2/favicons?domain=${source.source_url}&sz=64`,
    sourceUrl: source.source_url,
    products: source.results.map((result) => ({
      title: result.name,
      image: result.image_link ?? null,
      characteristics: Object.entries(result.characteristics ?? {}).map(
        ([name, value]) => `${name}: ${value}`,
      ),
      productLink: result.product_link,
      price: result.price,
      rating: result.rating,
      reviews: result.reviews,
    })),
  };
}

const exampleSearchResults = JSON.parse(
  exampleSearchResultsRaw,
) as SchemaSearchResults;
const marketplaceGroups = exampleSearchResults.sources.map(
  mapSearchSourceToGroup,
);

function Home() {
  const [searchInput, setSearchInput] = useState("");
  const [searchParams, setSearchParams] = useState<{
    query: string;
    region: string | null;
  } | null>(null);
  const [selectedRegion, setSelectedRegion] = useState(ALL_REGIONS);
  const {
    data: searchResults,
    error,
    isFetching,
  } = $api.useQuery(
    "post",
    "/search/search",
    {
      body: searchParams ?? {
        query: "",
        region: null,
      },
    },
    {
      enabled: searchParams !== null,
    },
  );
  const apiSourceGroups = searchResults?.sources.map(mapSearchSourceToGroup);
  const visibleGroups = apiSourceGroups ?? marketplaceGroups;

  const totalProducts = visibleGroups.reduce(
    (sum, group) => sum + group.products.length,
    0,
  );
  const isSearchDisabled = isFetching || searchInput.trim().length === 0;

  const handleSearchSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const query = searchInput.trim();

    if (!query) return;

    setSearchParams({
      query,
      region: selectedRegion === ALL_REGIONS ? null : selectedRegion,
    });
  };

  return (
    <main className="min-h-screen bg-background text-foreground">
      <section className="mx-auto flex w-full max-w-7xl flex-col gap-8 px-4 py-8 sm:px-6 lg:px-8">
        <header className="flex flex-col gap-3">
          <div className="max-w-3xl">
            <h1 className="text-3xl font-semibold tracking-tight text-slate-950 sm:text-4xl">
              Поиск товаров по Рунету
            </h1>
          </div>
        </header>

        <form
          aria-label="Фильтры каталога"
          className="grid gap-4 rounded-lg border border-slate-200 bg-white p-4 shadow-sm md:grid-cols-[minmax(0,1fr)_320px_auto]"
          onSubmit={handleSearchSubmit}
        >
          <label className="flex flex-col gap-2">
            <span className="text-sm font-medium text-slate-700">
              Строка поиска
            </span>
            <span className="relative">
              <Search
                aria-hidden="true"
                className="pointer-events-none absolute left-3 top-1/2 size-5 -translate-y-1/2 text-slate-400"
              />
              <input
                className="h-11 w-full rounded-md border border-slate-300 bg-white pl-10 pr-3 text-sm outline-none transition focus:border-slate-900 focus:ring-2 focus:ring-slate-900/10"
                onChange={(event) => setSearchInput(event.target.value)}
                placeholder="Введите товар или характеристику"
                type="search"
                value={searchInput}
              />
            </span>
          </label>

          <RegionDropdown
            onSelect={setSelectedRegion}
            selectedRegion={selectedRegion}
          />

          <div className="flex flex-col justify-end">
            <Button
              className="h-11 w-full gap-2 px-4 text-sm md:min-w-32"
              disabled={isSearchDisabled}
              type="submit"
            >
              {isFetching ? (
                <LoaderCircle
                  aria-hidden="true"
                  className="size-4 animate-spin"
                />
              ) : (
                <Search aria-hidden="true" className="size-4" />
              )}
              {isFetching ? "Ищем..." : "Найти"}
            </Button>
          </div>
        </form>

        <section className="flex flex-col gap-4" aria-label="Источники товаров">
          <div className="flex flex-col gap-1 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <h2 className="text-xl font-semibold text-slate-950">
                Основные источники
              </h2>
              <p className="text-sm text-slate-600">Регион: {selectedRegion}</p>
            </div>
            <p className="text-sm text-slate-500">
              {isFetching
                ? "Идёт поиск..."
                : `Найдено товаров: ${totalProducts}`}
            </p>
          </div>

          {error ? (
            <p className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
              Не удалось выполнить поиск. Попробуйте ещё раз.
            </p>
          ) : null}

          {visibleGroups.map((group) => (
            <ProductSourceDetails group={group} key={group.title} />
          ))}
        </section>
      </section>
    </main>
  );
}
