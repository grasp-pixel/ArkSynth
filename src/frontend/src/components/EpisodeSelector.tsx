import { useEffect, useState } from 'react'
import { useAppStore } from '../stores/appStore'

export default function EpisodeSelector() {
  const {
    backendStatus,
    categories,
    selectedCategoryId,
    storyGroups,
    selectedGroupId,
    groupEpisodes,
    selectedEpisodeId,
    isLoadingCategories,
    isLoadingGroups,
    isLoadingGroupEpisodes,
    loadCategories,
    selectCategory,
    selectStoryGroup,
    selectEpisode,
  } = useAppStore()

  const [expandedGroups, setExpandedGroups] = useState<Set<string>>(new Set())
  const [searchTerm, setSearchTerm] = useState('')

  useEffect(() => {
    if (backendStatus === 'connected') {
      loadCategories()
    }
  }, [backendStatus, loadCategories])

  const toggleGroup = (groupId: string) => {
    setExpandedGroups((prev) => {
      const next = new Set(prev)
      if (next.has(groupId)) {
        next.delete(groupId)
      } else {
        next.add(groupId)
        selectStoryGroup(groupId)
      }
      return next
    })
  }

  const filteredGroups = storyGroups.filter((group) => {
    if (!searchTerm) return true
    const term = searchTerm.toLowerCase()
    return group.name.toLowerCase().includes(term)
  })

  if (backendStatus !== 'connected') {
    return (
      <div className="flex flex-col items-center justify-center h-full p-8 text-center">
        <svg viewBox="0 0 24 24" className="w-12 h-12 text-red-500 mb-4" fill="currentColor">
          <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z"/>
        </svg>
        <p className="text-ark-white mb-2">서버 연결 안됨</p>
        <p className="text-sm text-ark-gray">백엔드 서버를 실행해주세요</p>
      </div>
    )
  }

  return (
    <div className="flex flex-col h-full">
      {/* 카테고리 탭 */}
      <div className="flex border-b border-ark-border overflow-x-auto bg-ark-black/50">
        {isLoadingCategories ? (
          <div className="p-3 text-ark-gray text-sm ark-pulse">로딩 중...</div>
        ) : (
          categories.map((cat) => (
            <button
              key={cat.id}
              onClick={() => selectCategory(cat.id)}
              className={`px-4 py-2.5 text-sm font-medium whitespace-nowrap transition-all border-b-2 ${
                selectedCategoryId === cat.id
                  ? 'bg-ark-orange/10 text-ark-orange border-ark-orange'
                  : 'text-ark-gray hover:text-ark-white hover:bg-ark-panel/50 border-transparent'
              }`}
            >
              {cat.name}
              <span className="ml-1.5 text-xs opacity-70">({cat.group_count})</span>
            </button>
          ))
        )}
      </div>

      {/* 검색 */}
      <div className="p-4 border-b border-ark-border">
        <div className="relative">
          <input
            type="text"
            placeholder="스토리 검색..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="ark-input pl-10"
          />
          <svg viewBox="0 0 24 24" className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-ark-gray" fill="currentColor">
            <path d="M15.5 14h-.79l-.28-.27C15.41 12.59 16 11.11 16 9.5 16 5.91 13.09 3 9.5 3S3 5.91 3 9.5 5.91 16 9.5 16c1.61 0 3.09-.59 4.23-1.57l.27.28v.79l5 4.99L20.49 19l-4.99-5zm-6 0C7.01 14 5 11.99 5 9.5S7.01 5 9.5 5 14 7.01 14 9.5 11.99 14 9.5 14z"/>
          </svg>
        </div>
      </div>

      {/* 스토리 그룹 목록 */}
      <div className="flex-1 overflow-y-auto">
        {isLoadingGroups ? (
          <div className="flex items-center justify-center h-32 text-ark-gray">
            <div className="ark-pulse">로딩 중...</div>
          </div>
        ) : filteredGroups.length === 0 ? (
          <div className="flex items-center justify-center h-32 text-ark-gray">
            {searchTerm ? '검색 결과 없음' : '스토리 없음'}
          </div>
        ) : (
          <div>
            {filteredGroups.map((group) => (
              <div key={group.id} className="border-b border-ark-border/50">
                {/* 그룹 헤더 */}
                <button
                  onClick={() => toggleGroup(group.id)}
                  className={`w-full px-4 py-3 text-left transition-all flex items-center justify-between group ${
                    selectedGroupId === group.id
                      ? 'bg-ark-panel'
                      : 'bg-ark-panel/30 hover:bg-ark-panel/50'
                  }`}
                >
                  <span className="font-medium text-ark-white truncate">{group.name}</span>
                  <span className="flex items-center gap-2 text-ark-gray text-sm flex-shrink-0 ml-2">
                    <span className="ark-badge">{group.episode_count}</span>
                    <span className="transition-transform duration-200" style={{
                      transform: expandedGroups.has(group.id) ? 'rotate(90deg)' : 'rotate(0deg)'
                    }}>▶</span>
                  </span>
                </button>

                {/* 에피소드 목록 */}
                {expandedGroups.has(group.id) && (
                  <div className="bg-ark-black/30">
                    {isLoadingGroupEpisodes && selectedGroupId === group.id ? (
                      <div className="p-4 text-center text-ark-gray text-sm ark-pulse">
                        로딩 중...
                      </div>
                    ) : (
                      <ul>
                        {groupEpisodes.map((ep) => (
                          <li key={ep.id}>
                            <button
                              onClick={() => selectEpisode(ep.id)}
                              className={`w-full px-6 py-3 text-left transition-all ${
                                selectedEpisodeId === ep.id
                                  ? 'ark-selected'
                                  : 'hover:bg-ark-panel/30'
                              }`}
                            >
                              <div className="flex items-center gap-2">
                                {ep.code && (
                                  <span className="font-medium text-ark-orange text-sm">
                                    {ep.code}
                                  </span>
                                )}
                                <span className="truncate text-ark-white">{ep.name}</span>
                              </div>
                              {ep.tag && (
                                <div className="text-xs text-ark-gray mt-1">
                                  {ep.tag}
                                </div>
                              )}
                            </button>
                          </li>
                        ))}
                      </ul>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* 통계 */}
      <div className="p-3 border-t border-ark-border bg-ark-black/50 text-xs text-ark-gray flex items-center justify-between">
        {selectedCategoryId && (
          <>
            <span>{categories.find((c) => c.id === selectedCategoryId)?.name}</span>
            <span>{storyGroups.length}개 스토리</span>
          </>
        )}
      </div>
    </div>
  )
}
