import { $api, apiFetch } from '@/api'
import { JobStatus, type SchemaJobInfo, type SchemaSearchParams } from '@/api/openapi.gen'
import { useQueryClient } from '@tanstack/react-query'
import { useEffect, useRef } from 'react'

const POLL_INTERVAL_MS = 500

type UseSearchJobOptions = {
  jobId: number | undefined
  setJobId: (jobId: number | undefined) => void
}

export function useSearchJob({ jobId, setJobId }: UseSearchJobOptions) {
  const queryClient = useQueryClient()
  const activeJobIdRef = useRef<number | undefined>(jobId)

  useEffect(() => {
    activeJobIdRef.current = jobId
  }, [jobId])

  const {
    mutate,
    isPending: isStarting,
    error: startError,
    reset: resetStart
  } = $api.useMutation('post', '/search/jobs/start')

  const {
    data: jobInfo,
    error: pollError,
    refetch
  } = $api.useQuery('get', '/search/jobs/{job_id}', {
    params: { path: { job_id: jobId ?? 0 } },
    enabled: jobId !== undefined,
    staleTime: 0,
    gcTime: 0
  })

  useEffect(() => {
    if (jobId === undefined) return
    if (jobInfo?.job_status === JobStatus.FINISHED) return

    const timer = window.setInterval(() => {
      void refetch()
    }, POLL_INTERVAL_MS)

    return () => window.clearInterval(timer)
  }, [jobId, jobInfo?.job_status, refetch])

  useEffect(() => {
    if (!pollError || jobId === undefined) return
    setJobId(undefined)
  }, [pollError, jobId, setJobId])

  const cancelJob = async (id: number) => {
    try {
      await apiFetch.POST('/search/jobs/{job_id}/cancel', {
        params: { path: { job_id: id } }
      })
    } catch {
      // Ignore cancel errors for stale jobs.
    }
  }

  const startSearch = (params: SchemaSearchParams) => {
    void (async () => {
      const previousJobId = activeJobIdRef.current
      if (previousJobId !== undefined) {
        await cancelJob(previousJobId)
      }
      resetStart()
      setJobId(undefined)
      mutate(
        { body: params },
        {
          onSuccess: (data: SchemaJobInfo) => {
            queryClient.setQueryData(
              $api.queryOptions('get', '/search/jobs/{job_id}', {
                params: { path: { job_id: data.job_id } }
              }).queryKey,
              data
            )
            setJobId(data.job_id)
          }
        }
      )
    })()
  }

  const isSearching =
    isStarting ||
    (jobId !== undefined &&
      (jobInfo === undefined || jobInfo.job_status === JobStatus.PENDING))

  return {
    jobInfo: jobId !== undefined && jobInfo?.job_id === jobId ? jobInfo : undefined,
    startSearch,
    isSearching,
    error: startError ?? pollError
  }
}
