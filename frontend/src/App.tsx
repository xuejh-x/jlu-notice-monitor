import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { AppShell } from './components/layout/AppShell'
import { DashboardPage } from './pages/DashboardPage'
import { TodayPage } from './pages/TodayPage'
import { DeadlinesPage } from './pages/DeadlinesPage'
import { CompetitionsPage } from './pages/CompetitionsPage'
import { FeedPage } from './pages/FeedPage'
import { FavoritesPage } from './pages/FavoritesPage'
import { NoticesPage } from './pages/NoticesPage'
import { SourcesPage } from './pages/SourcesPage'
import { SettingsPage } from './pages/SettingsPage'
import { NoticeDetailPage } from './pages/NoticeDetailPage'
import { TrainingPage } from './pages/TrainingPage'
import { ThemeProvider } from './stores/theme'
import { ToastProvider } from './stores/toast'
import { loadSettings } from './stores/settings'

const queryClient = new QueryClient({ defaultOptions: { queries: { staleTime: 30_000, retry: 1, refetchOnWindowFocus: false } } })
function HomeRoute() { const path = loadSettings().defaultHome; return path === '/' ? <DashboardPage /> : <Navigate to={path} replace /> }

export default function App() {
  return <QueryClientProvider client={queryClient}><ThemeProvider><ToastProvider><BrowserRouter><Routes>
    <Route element={<AppShell />}>
      <Route index element={<HomeRoute />} />
      <Route path="today" element={<TodayPage />} />
      <Route path="deadlines" element={<DeadlinesPage />} />
      <Route path="competitions" element={<CompetitionsPage />} />
      <Route path="competitions/algorithm" element={<FeedPage title="算法竞赛" description="聚合蓝桥杯、天梯赛、ICPC、CCPC、CSP 等程序设计竞赛。" categories={['algorithm_competition']} />} />
      <Route path="algorithm" element={<Navigate to="/competitions/algorithm" replace />} />
      <Route path="cybersecurity" element={<FeedPage title="网络安全" description="聚合 CTF、密码学、攻防、安全实训和数据安全通知。" categories={['cybersecurity_competition']} />} />
      <Route path="training" element={<TrainingPage />} />
      <Route path="research" element={<FeedPage title="科研与实验室" description="聚合科研项目、实验室招募、学生创新项目和大创信息。" categories={['research']} />} />
      <Route path="postgraduate" element={<FeedPage title="推免与评奖" description="集中查看推免政策、竞赛加分、课程免修和评奖相关通知。" categories={['postgraduate_recommendation']} />} />
      <Route path="favorites" element={<FavoritesPage />} />
      <Route path="notices" element={<NoticesPage />} />
      <Route path="notices/:id" element={<NoticeDetailPage />} />
      <Route path="sources" element={<SourcesPage />} />
      <Route path="settings" element={<SettingsPage />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Route>
  </Routes></BrowserRouter></ToastProvider></ThemeProvider></QueryClientProvider>
}
