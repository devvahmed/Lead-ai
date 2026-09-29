import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  typescript: {
    ignoreBuildErrors: true,
  },
  turbopack: {},
  webpack: (config, { dev }) => {
    if (dev) {
      config.watchOptions = {
        ignored: [
          '**/.git/**',
          '**/node_modules/**',
          '**/.next/**',
          '**/backend/**',
          '**/scratch/**',
          '**/*.db',
          '**/*.db-journal',
          '**/*.db-wal',
          '**/*.csv',
          '**/processed_domains.json',
        ],
      };
    }
    return config;
  },
  // Allow LAN access from client PCs so dev resources and React hydration execute properly
  allowedDevOrigins: [
    '100.91.220.98',
    '100.91.220.98:3000',
    '192.168.0.112',
    '192.168.0.112:3000',
    '192.168.0.107',
    '192.168.0.107:3000',
    '192.168.100.13',
    '192.168.100.13:3000',
    'localhost',
    'localhost:3000',
    '127.0.0.1',
    '127.0.0.1:3000',
  ],
  images: {
    remotePatterns: [
      {
        protocol: 'https',
        hostname: 'logo.clearbit.com',
        pathname: '/**',
      },
      {
        protocol: 'https',
        hostname: 'www.google.com',
        pathname: '/s2/favicons/**',
      },
    ],
  },
};

export default nextConfig;
