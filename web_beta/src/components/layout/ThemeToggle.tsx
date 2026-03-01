import { Moon, Sun } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { useStore } from '@/store'

export function ThemeToggle() {
  const theme = useStore(s => s.theme)
  const toggleTheme = useStore(s => s.toggleTheme)

  return (
    <Button variant="ghost" size="icon" onClick={toggleTheme} title="Toggle theme">
      {theme === 'dark' ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
    </Button>
  )
}
