import { createFileRoute } from '@tanstack/react-router'
import { ChevronDown, Search } from 'lucide-react'
import { useState } from 'react'

export const Route = createFileRoute('/')({ component: Home })

type Product = {
  title: string
  image: string
  characteristics: string[]
}

type MarketplaceGroup = {
  title: string
  logoUrl: string
  products: Product[]
}

const OTHER_SOURCES_STEP = 10

const regions = [
  'Все регионы',
  'Алтайский край',
  'Амурская область',
  'Архангельская область',
  'Астраханская область',
  'Белгородская область',
  'Брянская область',
  'Владимирская область',
  'Волгоградская область',
  'Вологодская область',
  'Воронежская область',
  'Донецкая Народная Республика',
  'Еврейская автономная область',
  'Забайкальский край',
  'Запорожская область',
  'Ивановская область',
  'Иркутская область',
  'Кабардино-Балкарская Республика',
  'Калининградская область',
  'Калужская область',
  'Камчатский край',
  'Карачаево-Черкесская Республика',
  'Кемеровская область',
  'Кировская область',
  'Костромская область',
  'Краснодарский край',
  'Красноярский край',
  'Курганская область',
  'Курская область',
  'Ленинградская область',
  'Липецкая область',
  'Луганская Народная Республика',
  'Магаданская область',
  'Москва',
  'Московская область',
  'Мурманская область',
  'Ненецкий автономный округ',
  'Нижегородская область',
  'Новгородская область',
  'Новосибирская область',
  'Омская область',
  'Оренбургская область',
  'Орловская область',
  'Пензенская область',
  'Пермский край',
  'Приморский край',
  'Псковская область',
  'Республика Адыгея',
  'Республика Алтай',
  'Республика Башкортостан',
  'Республика Бурятия',
  'Республика Дагестан',
  'Республика Ингушетия',
  'Республика Калмыкия',
  'Республика Карелия',
  'Республика Коми',
  'Республика Крым',
  'Республика Марий Эл',
  'Республика Мордовия',
  'Республика Саха (Якутия)',
  'Республика Северная Осетия - Алания',
  'Республика Татарстан',
  'Республика Тыва',
  'Республика Хакасия',
  'Ростовская область',
  'Рязанская область',
  'Самарская область',
  'Санкт-Петербург',
  'Саратовская область',
  'Сахалинская область',
  'Свердловская область',
  'Севастополь',
  'Смоленская область',
  'Ставропольский край',
  'Тамбовская область',
  'Тверская область',
  'Томская область',
  'Тульская область',
  'Тюменская область',
  'Удмуртская Республика',
  'Ульяновская область',
  'Хабаровский край',
  'Ханты-Мансийский автономный округ - Югра',
  'Херсонская область',
  'Челябинская область',
  'Чеченская Республика',
  'Чувашская Республика',
  'Чукотский автономный округ',
  'Ямало-Ненецкий автономный округ',
  'Ярославская область'
]

const marketplaceGroups: MarketplaceGroup[] = [
  {
    title: 'Яндекс.Маркет',
    logoUrl: 'https://www.google.com/s2/favicons?domain=market.yandex.ru&sz=64',
    products: [
      {
        title: 'Ноутбук Lenovo IdeaPad Slim 3',
        image:
          'https://images.unsplash.com/photo-1496181133206-80ce9b88a853?auto=format&fit=crop&w=900&q=80',
        characteristics: [
          'Экран: 15.6", Full HD',
          'Процессор: Intel Core i5',
          'Оперативная память: 16 ГБ'
        ]
      },
      {
        title: 'Монитор Samsung ViewFinity 27',
        image:
          'https://images.unsplash.com/photo-1527443224154-c4a3942d3acf?auto=format&fit=crop&w=900&q=80',
        characteristics: ['Диагональ: 27"', 'Разрешение: 2560 x 1440', 'Частота обновления: 75 Гц']
      },
      {
        title: 'МФУ HP LaserJet Pro',
        image:
          'https://images.unsplash.com/photo-1612815154858-60aa4c59eaa6?auto=format&fit=crop&w=900&q=80',
        characteristics: ['Тип печати: лазерная', 'Формат: A4', 'Скорость: до 29 стр/мин']
      }
    ]
  },
  {
    title: 'Ozon',
    logoUrl: 'https://www.google.com/s2/favicons?domain=ozon.ru&sz=64',
    products: [
      {
        title: 'Кресло офисное Chairman Ergo',
        image:
          'https://images.unsplash.com/photo-1580480055273-228ff5388ef8?auto=format&fit=crop&w=900&q=80',
        characteristics: [
          'Материал: экокожа и текстиль',
          'Механизм: качание',
          'Нагрузка: до 120 кг'
        ]
      },
      {
        title: 'Клавиатура Logitech MX Keys',
        image:
          'https://images.unsplash.com/photo-1587829741301-dc798b83add3?auto=format&fit=crop&w=900&q=80',
        characteristics: ['Тип: беспроводная', 'Подключение: Bluetooth', 'Подсветка: есть']
      },
      {
        title: 'Веб-камера Full HD 1080p',
        image:
          'https://images.unsplash.com/photo-1611532736597-de2d4265fba3?auto=format&fit=crop&w=900&q=80',
        characteristics: [
          'Разрешение: 1920 x 1080',
          'Микрофон: встроенный',
          'Крепление: универсальное'
        ]
      }
    ]
  },
  {
    title: 'Wildberries',
    logoUrl: 'https://www.google.com/s2/favicons?domain=wildberries.ru&sz=64',
    products: [
      {
        title: 'Роутер TP-Link Archer AX23',
        image:
          'https://images.unsplash.com/photo-1544197150-b99a580bb7a8?auto=format&fit=crop&w=900&q=80',
        characteristics: ['Стандарт: Wi-Fi 6', 'Скорость: до 1800 Мбит/с', 'Диапазоны: 2.4 и 5 ГГц']
      },
      {
        title: 'Наушники Sony WH-CH720N',
        image:
          'https://images.unsplash.com/photo-1505740420928-5e560c06d30e?auto=format&fit=crop&w=900&q=80',
        characteristics: [
          'Тип: полноразмерные',
          'Шумоподавление: активное',
          'Время работы: до 35 часов'
        ]
      },
      {
        title: 'Портативный SSD Samsung T7',
        image:
          'https://images.unsplash.com/photo-1597872200969-2b65d56bd16b?auto=format&fit=crop&w=900&q=80',
        characteristics: ['Объем: 1 ТБ', 'Интерфейс: USB 3.2', 'Скорость чтения: до 1050 МБ/с']
      }
    ]
  }
]

const otherSourceGroups: MarketplaceGroup[] = [
  {
    title: 'Ситилинк',
    logoUrl: 'https://www.google.com/s2/favicons?domain=citilink.ru&sz=64',
    products: [
      {
        title: 'Системный блок iRU Office',
        image:
          'https://images.unsplash.com/photo-1593640495253-23196b27a87f?auto=format&fit=crop&w=900&q=80',
        characteristics: ['Процессор: Intel Core i5', 'ОЗУ: 16 ГБ', 'Накопитель: SSD 512 ГБ']
      }
    ]
  },
  {
    title: 'DNS',
    logoUrl: 'https://www.google.com/s2/favicons?domain=dns-shop.ru&sz=64',
    products: [
      {
        title: 'Коммутатор TP-Link TL-SG108',
        image:
          'https://images.unsplash.com/photo-1544197150-b99a580bb7a8?auto=format&fit=crop&w=900&q=80',
        characteristics: [
          'Порты: 8 x Gigabit Ethernet',
          'Корпус: металлический',
          'Питание: внешний адаптер'
        ]
      }
    ]
  },
  {
    title: 'М.Видео',
    logoUrl: 'https://www.google.com/s2/favicons?domain=mvideo.ru&sz=64',
    products: [
      {
        title: 'Проектор Epson EB-FH52',
        image:
          'https://images.unsplash.com/photo-1601944179066-29786cb9d32a?auto=format&fit=crop&w=900&q=80',
        characteristics: ['Разрешение: Full HD', 'Яркость: 4000 лм', 'Интерфейсы: HDMI, USB']
      }
    ]
  },
  {
    title: 'Эльдорадо',
    logoUrl: 'https://www.google.com/s2/favicons?domain=eldorado.ru&sz=64',
    products: [
      {
        title: 'Телевизор LG 55UR78006LK',
        image:
          'https://images.unsplash.com/photo-1593305841991-05c297ba4575?auto=format&fit=crop&w=900&q=80',
        characteristics: ['Диагональ: 55"', 'Разрешение: 4K UHD', 'Smart TV: есть']
      }
    ]
  },
  {
    title: 'ВсеИнструменты.ру',
    logoUrl: 'https://www.google.com/s2/favicons?domain=vseinstrumenti.ru&sz=64',
    products: [
      {
        title: 'Набор инструментов Gross 82 предмета',
        image:
          'https://images.unsplash.com/photo-1530124566582-a618bc2615dc?auto=format&fit=crop&w=900&q=80',
        characteristics: [
          'Количество предметов: 82',
          'Материал: хром-ванадиевая сталь',
          'Упаковка: пластиковый кейс'
        ]
      }
    ]
  },
  {
    title: 'Комус',
    logoUrl: 'https://www.google.com/s2/favicons?domain=komus.ru&sz=64',
    products: [
      {
        title: 'Бумага офисная Ballet Classic A4',
        image:
          'https://images.unsplash.com/photo-1586075010923-2dd4570fb338?auto=format&fit=crop&w=900&q=80',
        characteristics: ['Формат: A4', 'Плотность: 80 г/м2', 'Упаковка: 500 листов']
      }
    ]
  },
  {
    title: 'Леруа Мерлен',
    logoUrl: 'https://www.google.com/s2/favicons?domain=leroymerlin.ru&sz=64',
    products: [
      {
        title: 'Светильник светодиодный офисный',
        image:
          'https://images.unsplash.com/photo-1524484485831-a92ffc0de03f?auto=format&fit=crop&w=900&q=80',
        characteristics: ['Мощность: 36 Вт', 'Температура: 4000 К', 'Монтаж: накладной']
      }
    ]
  },
  {
    title: 'Петрович',
    logoUrl: 'https://www.google.com/s2/favicons?domain=petrovich.ru&sz=64',
    products: [
      {
        title: 'Стеллаж металлический Практик',
        image:
          'https://images.unsplash.com/photo-1586023492125-27b2c045efd7?auto=format&fit=crop&w=900&q=80',
        characteristics: [
          'Полки: 5 шт.',
          'Нагрузка на полку: до 100 кг',
          'Материал: оцинкованная сталь'
        ]
      }
    ]
  },
  {
    title: 'Яндекс Лавка для бизнеса',
    logoUrl: 'https://www.google.com/s2/favicons?domain=lavka.yandex.ru&sz=64',
    products: [
      {
        title: 'Набор питьевой воды для офиса',
        image:
          'https://images.unsplash.com/photo-1559839914-17aae19cec71?auto=format&fit=crop&w=900&q=80',
        characteristics: ['Объем: 0.5 л', 'Количество: 24 бутылки', 'Категория: напитки']
      }
    ]
  },
  {
    title: 'СберМегаМаркет',
    logoUrl: 'https://www.google.com/s2/favicons?domain=megamarket.ru&sz=64',
    products: [
      {
        title: 'Кофемашина DeLonghi Magnifica',
        image:
          'https://images.unsplash.com/photo-1517668808822-9ebb02f2a0e6?auto=format&fit=crop&w=900&q=80',
        characteristics: ['Тип: автоматическая', 'Капучинатор: есть', 'Контейнер для зерен: 250 г']
      }
    ]
  },
  {
    title: 'Регард',
    logoUrl: 'https://www.google.com/s2/favicons?domain=regard.ru&sz=64',
    products: [
      {
        title: 'ИБП APC Back-UPS 950VA',
        image:
          'https://images.unsplash.com/photo-1621905252507-b35492cc74b4?auto=format&fit=crop&w=900&q=80',
        characteristics: ['Мощность: 950 ВА', 'Розетки: 6 шт.', 'Защита: от скачков напряжения']
      }
    ]
  },
  {
    title: 'ОнлайнТрейд',
    logoUrl: 'https://www.google.com/s2/favicons?domain=onlinetrade.ru&sz=64',
    products: [
      {
        title: 'Док-станция Baseus USB-C',
        image:
          'https://images.unsplash.com/photo-1619953942547-233eab5a70d6?auto=format&fit=crop&w=900&q=80',
        characteristics: [
          'Порты: HDMI, USB-A, USB-C',
          'Питание: Power Delivery',
          'Материал: алюминий'
        ]
      }
    ]
  }
]

function RegionDropdown({
  selectedRegion,
  onSelect
}: {
  selectedRegion: string
  onSelect: (region: string) => void
}) {
  const [isOpen, setIsOpen] = useState(false)

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
          className={`size-4 shrink-0 text-slate-500 transition ${isOpen ? 'rotate-180' : ''}`}
        />
      </button>

      {isOpen ? (
        <div className="absolute left-0 right-0 top-full z-20 mt-2 max-h-72 overflow-y-auto rounded-md border border-slate-200 bg-white py-1 shadow-lg">
          {regions.map((region, index) => (
            <button
              className={`block w-full px-3 py-2 text-left text-sm transition hover:bg-slate-100 ${
                region === selectedRegion ? 'font-medium text-slate-950' : 'text-slate-700'
              } ${index === 0 ? 'sticky top-0 z-10 border-b border-slate-200 bg-white' : ''}`}
              key={region}
              onClick={() => {
                onSelect(region)
                setIsOpen(false)
              }}
              type="button"
            >
              {region}
            </button>
          ))}
        </div>
      ) : null}
    </div>
  )
}

function ProductSourceDetails({ group }: { group: MarketplaceGroup }) {
  return (
    <details className="group rounded-lg border border-slate-200 bg-white shadow-sm" open>
      <summary className="flex cursor-pointer list-none items-center justify-between gap-4 px-4 py-4 marker:hidden">
        <span className="flex min-w-0 items-center gap-3">
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
        <span className="rounded-full border border-slate-200 px-3 py-1 text-sm text-slate-600">
          {group.products.length}
        </span>
      </summary>

      <div className="border-t border-slate-200 p-4">
        {group.products.length > 0 ? (
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {group.products.map((product) => (
              <article
                className="overflow-hidden rounded-lg border border-slate-200 bg-white"
                key={product.title}
              >
                <img
                  alt={product.title}
                  className="h-44 w-full object-cover"
                  loading="lazy"
                  src={product.image}
                />
                <div className="flex flex-col gap-3 p-4">
                  <h3 className="text-base font-semibold leading-6 text-slate-950">
                    {product.title}
                  </h3>
                  <ul className="space-y-1 text-sm text-slate-600">
                    {product.characteristics.map((characteristic) => (
                      <li className="border-l border-slate-200 pl-3 leading-5" key={characteristic}>
                        {characteristic}
                      </li>
                    ))}
                  </ul>
                </div>
              </article>
            ))}
          </div>
        ) : (
          <p className="rounded-md bg-slate-50 px-4 py-6 text-center text-sm text-slate-500">
            Ничего не найдено по текущему запросу.
          </p>
        )}
      </div>
    </details>
  )
}

function Home() {
  const [selectedRegion, setSelectedRegion] = useState('Все регионы')
  const [visibleOtherSources, setVisibleOtherSources] = useState(OTHER_SOURCES_STEP)

  const visibleOtherSourceGroups = otherSourceGroups.slice(0, visibleOtherSources)
  const hiddenOtherSourcesCount = Math.max(otherSourceGroups.length - visibleOtherSources, 0)
  const totalProducts = [...marketplaceGroups, ...otherSourceGroups].reduce(
    (sum, group) => sum + group.products.length,
    0
  )

  return (
    <main className="min-h-screen bg-slate-50 text-slate-950">
      <section className="mx-auto flex w-full max-w-7xl flex-col gap-8 px-4 py-8 sm:px-6 lg:px-8">
        <header className="flex flex-col gap-3">
          <div className="max-w-3xl">
            <h1 className="text-3xl font-semibold tracking-tight text-slate-950 sm:text-4xl">
              Поиск товаров по Рунету
            </h1>
          </div>
        </header>

        <section
          aria-label="Фильтры каталога"
          className="grid gap-4 rounded-lg border border-slate-200 bg-white p-4 shadow-sm md:grid-cols-[1fr_320px]"
        >
          <label className="flex flex-col gap-2">
            <span className="text-sm font-medium text-slate-700">Строка поиска</span>
            <span className="relative">
              <Search
                aria-hidden="true"
                className="pointer-events-none absolute left-3 top-1/2 size-5 -translate-y-1/2 text-slate-400"
              />
              <input
                className="h-11 w-full rounded-md border border-slate-300 bg-white pl-10 pr-3 text-sm outline-none transition focus:border-slate-900 focus:ring-2 focus:ring-slate-900/10"
                placeholder="Введите товар или характеристику"
                type="search"
              />
            </span>
          </label>

          <RegionDropdown onSelect={setSelectedRegion} selectedRegion={selectedRegion} />
        </section>

        <section className="flex flex-col gap-4" aria-label="Источники товаров">
          <div className="flex flex-col gap-1 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <h2 className="text-xl font-semibold text-slate-950">Основные источники</h2>
              <p className="text-sm text-slate-600">Регион: {selectedRegion}</p>
            </div>
            <p className="text-sm text-slate-500">Найдено товаров: {totalProducts}</p>
          </div>

          {marketplaceGroups.map((group) => (
            <ProductSourceDetails group={group} key={group.title} />
          ))}

          <h2 className="pt-3 text-xl font-semibold text-slate-950">Другие источники</h2>

          {visibleOtherSourceGroups.map((group) => (
            <ProductSourceDetails group={group} key={group.title} />
          ))}

          {hiddenOtherSourcesCount > 0 ? (
            <button
              className="self-center rounded-md border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-800 shadow-sm transition hover:bg-slate-100 focus:outline-none focus:ring-2 focus:ring-slate-900/10"
              onClick={() => setVisibleOtherSources((current) => current + OTHER_SOURCES_STEP)}
              type="button"
            >
              Показать ещё ({hiddenOtherSourcesCount} источников)
            </button>
          ) : null}
        </section>
      </section>
    </main>
  )
}
