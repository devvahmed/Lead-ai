import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  typescript: {
    ignoreBuildErrors: true,
  },
  // Allow LAN access from client PCs so dev resources and React hydration execute properly
  allowedDevOrigins: [
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
