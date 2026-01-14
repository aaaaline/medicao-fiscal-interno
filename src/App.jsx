import { useState } from 'react'

import "./App.css";
import Search from './components/search';

function App() {

  return (
      <div className="app">
        <h1>Consulta Medição Fiscal</h1>
        <Search/>
        
      </div>
  )
}

export default App