import { meta } from "./data.js";
import SearchView from "./views/SearchView.jsx";
import "./App.css";

export default function App() {
  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <strong>건축 법령 탐색기</strong>
          <span className="metaline">
            검색 → 조문 → 근거·인용을 한 화면에 · {meta.law_count}개 법령 {meta.node_count}조문
          </span>
        </div>
      </header>

      <div className="stage">
        <SearchView />
      </div>

      <footer className="disclaimer">
        참고용 시각화입니다. 정확도·법적 효력을 주장하지 않으며, 실제 법령 검토는 원문을 확인하세요.
      </footer>
    </div>
  );
}
