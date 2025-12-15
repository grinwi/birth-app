/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  eslint: {
    ignoreDuringBuilds: true
  },
  async rewrites() {
    return [
      { source: '/api-py/health', destination: '/api/health.py' },
      { source: '/api-py/people', destination: '/api/people.py' },
      { source: '/api-py/people/:index', destination: '/api/people_index.py?index=:index' },
      { source: '/api-py/csv', destination: '/api/csv.py' },
      { source: '/api-py/auth/login', destination: '/api/auth/login.py' },
      { source: '/api-py/auth/invite', destination: '/api/auth/invite.py' },
      { source: '/api-py/auth/register', destination: '/api/auth/register.py' }
    ];
  }
};

export default nextConfig;
