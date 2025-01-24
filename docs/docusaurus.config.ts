import {themes as prismThemes} from 'prism-react-renderer';
import type {Config} from '@docusaurus/types';
import type * as Preset from '@docusaurus/preset-classic';

const config: Config = {
  title: 'Emma for Infrahub',
  tagline: 'Emma is an agent designed to help you interact with Infrahub',
  favicon: 'img/favicon.ico',

  // Set the production url of your site here
  url: 'https://your-docusaurus-site.example.com',
  // Set the /<baseUrl>/ pathname under which your site is served
  // For GitHub pages deployment, it is often '/<projectName>/'
  baseUrl: '/',

  organizationName: 'opsmill',
  projectName: 'emma',

  onBrokenLinks: 'throw',
  onBrokenMarkdownLinks: 'warn',
  onDuplicateRoutes: "throw",
  // Even if you don't use internationalization, you can use this field to set
  // useful metadata like html lang. For example, if your site is Chinese, you
  // may want to replace "en" with "zh-Hans".
  i18n: {
    defaultLocale: 'en',
    locales: ['en'],
  },

  presets: [
    [
      "classic",
      {
        docs: {
          // Please change this to your repo.
          // Remove this to remove the "edit this page" links.
          editUrl: "https://github.com/opsmill/emma/tree/main/docs",
          routeBasePath: "/",
          sidebarCollapsed: true,
          sidebarPath: "./sidebars.ts",
        },
        blog: false,
        theme: {
          customCss: "./src/css/custom.css",
        },
      } satisfies Preset.Options,
    ],
  ],

  themeConfig: {
    // announcementBar: {
    //   content: 'Welcome to our brand new docs!',
    //   isCloseable: true,
    // },
    navbar: {
      logo: {
        alt: "Infrahub",
        src: "img/infrahub-hori.svg",
        srcDark: "img/infrahub-hori-dark.svg",
      },
      items: [
        {
          type: "docSidebar",
          sidebarId: "docsSidebar",
          position: "left",
          label: "Emma",
        },
        // {
        //   type: "search",
        //   position: "right",
        // },
        {
          href: "https://github.com/opsmill/emma",
          position: "right",
          className: "header-github-link",
          "aria-label": "GitHub repository",
        },
      ],
    },
    footer: {
      copyright: `Copyright © ${new Date().getFullYear()} - <b>Infrahub</b> by OpsMill.`,
    },
    prism: {
      theme: prismThemes.oneDark,
      additionalLanguages: ["bash", "python", "markup-templating", "django", "json", "toml", "yaml"],
    },
  } satisfies Preset.ThemeConfig,
};

export default config;
