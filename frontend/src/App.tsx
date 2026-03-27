import { FluentProvider, webDarkTheme, Title1 } from '@fluentui/react-components'

export default function App() {
  return (
    <FluentProvider theme={webDarkTheme}>
      <div className="tw:flex tw:flex-col tw:min-h-screen tw:items-center tw:justify-center">
        <Title1>Atlas</Title1>
        <p className="tw:mt-4">React shell is running. Fluent UI and Tailwind are configured.</p>
      </div>
    </FluentProvider>
  )
}
