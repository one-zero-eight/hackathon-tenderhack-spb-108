export type Product = {
  title: string
  image: string
  characteristics: string[]
}

export type MarketplaceGroup = {
  title: string
  logoUrl: string
  products: Product[]
}

export const regions = [
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

export const marketplaceGroups: MarketplaceGroup[] = [
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

export const otherSourceGroups: MarketplaceGroup[] = [
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
