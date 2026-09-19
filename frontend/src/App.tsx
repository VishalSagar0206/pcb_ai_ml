import { Suspense, lazy, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { Loader2 } from 'lucide-react'
import AppHeader, { type TabId } from './components/layout/AppHeader'
import BoardExplorer from './components/layout/BoardExplorer'

// Secondary tabs are lazy-loaded: they aren't visible on first paint (Board
// Explorer is the default tab), so deferring their code -- notably
// EvaluationDashboard's ~600KB of Recharts -- keeps the initial bundle/paint
// fast for the common case of a user who only looks at Board Explorer.
const PipelinePage = lazy(() => import('./components/layout/PipelinePage'))
const EvaluationDashboard = lazy(() => import('./components/evaluation/EvaluationDashboard'))
const ResearchLineage = lazy(() => import('./components/research/ResearchLineage'))
const KnowledgeBasePage = lazy(() => import('./components/knowledge/KnowledgeBasePage'))

function TabFallback() {
  return (
    <div className="flex h-40 items-center justify-center text-slate-400">
      <Loader2 className="h-5 w-5 animate-spin text-teal-glow" />
    </div>
  )
}

function App() {
  const [tab, setTab] = useState<TabId>('board')

  return (
    <div className="mx-auto flex h-screen max-w-[1800px] flex-col overflow-hidden p-4">
      <AppHeader active={tab} onChange={setTab} />
      <main className="min-h-0 flex-1 overflow-y-auto pr-1">
        <AnimatePresence mode="wait">
          <motion.div
            key={tab}
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="h-full"
          >
            <Suspense fallback={<TabFallback />}>
              {tab === 'board' && <BoardExplorer />}
              {tab === 'pipeline' && <PipelinePage />}
              {tab === 'knowledge' && <KnowledgeBasePage />}
              {tab === 'evaluation' && <EvaluationDashboard />}
              {tab === 'research' && <ResearchLineage />}
            </Suspense>
          </motion.div>
        </AnimatePresence>
      </main>
    </div>
  )
}

export default App
